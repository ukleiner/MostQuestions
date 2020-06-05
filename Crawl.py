#potential for stealing session data
# 3 details needed for the login:
# username, sent as username
# password, sent as password
#logintoken, sent as logintoken, stored in name="logintoken" hidden inputfield
import re
import sys
import time
import argparse
from datetime import datetime
from collections import namedtuple
from requests import Session
import pandas as pd

Course = namedtuple('Course', 'id title link')
def id_from_link(link):
    return re.search(r'id=(\d*)', link).group(1)

def get_login_essentials(page_data):
    """gets the login token and login addr from the main page. currently works on moodle2/nu19 of HUJI
    Parameters:
        page_data (str) the response to GET request to a login page
    Returns:
    tuple (str, str): the login token and login address -> if is a real login page
    None -> if not login page
    TODO: regex fragile, should generalize
    """
    action_regex = r'<form.*id="login".*action="(\S*)"'
    token_regex = r'<input.*name="logintoken".*value="(\w*)"'

    try:
        # group 0 contains whole match, group 1 is the inner group
        action = re.search(action_regex, page_data).group(1)
        logintoken = re.search(token_regex, page_data).group(1)
        return (action, logintoken)
    except AttributeError:
        # Always make specific except errors to react only to EXPECTED errors, dont mute your code
        # Attribute error caused when we call group on a None object, the result of a failed search
        return None

def connect_to_moodle(action, usr, pswd, token, session):
    r = session.post(action, data = { "username": usr, "password": pswd, "logintoken":token })
    return r

def extract_courses_links(page):
    """ get links to all courses in the page
    Parameters:
    page (str) the content of a webpage
    Returns:
    list of tuples (id, title, link)
    or empty list if no links
    """
    course_regex = r'<a.*?title="([\w ]*)".*?href="(.*?)"'
    # returns list of tuples with both groups
    links = re.findall(course_regex, page)
    try:
        courses_links = [Course(id_from_link(link), title, link)  for title, link in links if re.search(r'course', link)]
        return courses_links
    except AttributeError:
        # accours if no link in page, re.search returns None that do not have group function
        return []

def extract_forum_links(session, course):
    """get ALL forums from course page, including Announcements

    Parameters:
    session: requests.Session, a Session object with an active session
    course: a namedtuple Course

    Returns:
        list of tuples (id, title, link, forum)
    """
    page = session.get(course.link)
    forum_regex = r'([.:/\w]*?/forum/view[.?=\w]*)'
    return [(course.id, course.title, course.link, forum) for forum in re.findall(forum_regex, page.text)]

def is_students_forum(forum):
    """ Is this a students questions forum?
    Parameters:
    forum str: html of forum

    Returns:
    True if student forum, false other ways

    Recognition of student forum is made using the #collapseAddForm href of the anchour to add a new post
    """
    students_regex = "#collapseAddForm"
    return re.search(students_regex, forum) is not None

def crawl_forum(forum, session):
    """ crawl a forum and get all questions, detects if it isn't a students forum and returns empty
    Parameters:
    session Session object, intialized
    forum Series with course id and link to forum
    Returns:
    A new DataFrame with [course id, forum id, user id, forum name, user name, question title, question time]
    """
    name_regex = r"<h2>(.*?)</h2>"
    discuss_regex = r'"([.:/\w]*?/discuss\.php\?d=(\d+))"'
    discussion_name_regex = r'class="discussionname">(.*?)</h3>'
    student_id_name_regex = r'/user/view\.php\?id=(\d+)[\w="&;]*>([\w ]+)'
    anonymous_regex = r'Anonymous'
    time_regex = r'<time>([, /:\w]+)</time>'
    # 02/02/2020 02:02
    hebrew_time_format = "%d/%m/%Y, %H:%M"
    # Monday, 17 February 2020, 02:02
    english_time_format = "%A, %d %B %Y, %H:%M"
    page = session.get(forum.forum).text
    discuss_data = []
    if is_students_forum(page):
        try:
            forum_id = id_from_link(forum.forum)
            forum_name = re.search(name_regex, page).group(1)
            discussions = re.findall(discuss_regex, page)
            for discuss_link, discuss_id in discussions:
                discuss = session.get(discuss_link).text
                try:
                    question_title = re.search(discussion_name_regex, discuss).group(1)
                    # two groups, first is uid, the second is student name
                    student_id_name = re.search(student_id_name_regex, discuss)
                    # happens when anonymous because we didnt authorized '-' in student name
                    if student_id_name is None:
                        student_id_name = re.search(anonymous_regex, discuss)
                        if student_id_name is not None:
                            student_id = -1
                            student_name = "Anonymous"
                    else:
                        student_id = student_id_name.group(1)
                        student_name = student_id_name.group(2)
                    # returns different formats in hebrew (only numbers and signs) and english (with words)
                    question_time = re.search(time_regex, discuss).group(1)
                    time_for_df = None
                    try:
                        # try hebrew time format
                        hebrew_time = datetime.strptime(question_time, hebrew_time_format)
                        time_for_df = hebrew_time
                    except ValueError:
                        try:
                            # not in hebrew time format, try in english format
                            english_time = datetime.strptime(question_time, english_time_format)
                            time_for_df = english_time
                        except ValueError:
                            # not in english, heck knows what
                            print(f"Wierd format, nothing I can do. date: {question_time}")

                    discuss_data.append((forum.id, forum_id, student_id, discuss_id, forum_name, student_name, question_title, time_for_df))
                except:
                    print(f"question #{discuss_id}: {question_title}. student: {student_id_name}. regex: {student_id_name_regex}")
                    print(sys.exc_info())
                    raise
        except:
            print("outer")
            print(sys.exc_info())
            raise
    # if not student forum discuss_data will be empty
    return pd.DataFrame(discuss_data, columns=["course", "forum", "student", "discuss", "forum_name", "student_name", "question", "time"])



def gather_discuss_data(addr, user, pswd, filename="discuss_data.csv"):
    session = Session()
    print("Starting")
    r = session.get(addr)
    action, logintoken = get_login_essentials(r.text)
    login = connect_to_moodle(action, user, pswd, logintoken, session)
    print(f"Logged in to {addr}")
    courses_links = extract_courses_links(login.text)
    print(f"{len(courses_links)} courses found")
    forum_links = [forum for course in courses_links for forum in extract_forum_links(session, course)]
    forums = pd.DataFrame(forum_links, columns=['id', 'title', 'link', 'forum'])
    print(f"{len(forums)} forums found, not all student forums")

    print("Extracting discuss data, might take a very long time.\n Don't interrupt")
    # To save bandwidth checking if student forum & extracting discuss is made in one round
    forum_discuss = forums.apply(crawl_forum, axis=1, args=(session,))
    print("Finished extracting. Making DataFrame")
    discuss_data = pd.concat(forum_discuss.array, ignore_index=True)
    discuss_data.to_csv(filename)
    print(f"DataFrame saved to file {filename}")
    return discuss_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", required=True, help="The address of the moodle site", dest='addr')
    parser.add_argument("-u", required=True, help="Username to login with", dest='username')
    parser.add_argument("-p", required=True, help="Password for username", dest='password')
    parser.add_argument("-f", help="filename to store discuss data produced", dest='filename')
    args = vars(parser.parse_args())

    if args['filename'] is None:
        del args['filename']

    print("This script making many HTTPS calls, make sure you have a steady internet connection.\n Prepare to wait alot.\n The script will update while moving from one step to another.\n ***NO NEED to stay near the computer***")
    start = time.time()
    discuss_data = gather_discuss_data(*args.values())
    end = time.time()
    print(f"Total running time: {end-start} sec")
