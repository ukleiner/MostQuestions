# MostQuestions
A tool for automatic discovery of the top student in asking questions.

Currently the project only has the crawler (Crawl.py)  which can be imported or used as a CLI tool.
The crawler saves the data to a csv file.
Use `python3 Crawl.py -h` for more information

## Future
1. Add the Analytics.py CLI tool
2. Add automated tests to both tools
3. Add support to more moodles
4. Make the calls to the moodle server async.
5. Allow sharing datasets automaticly from the CLI

## Known Issues
*maybe will be fixed*
1. Filtering of student forums might not work well for TA or Teachers due to the manner we detect a student forum
2. student names with special characters are not detected and might prevent the program from executing
