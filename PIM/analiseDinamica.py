import variablesPIM as variables
import createFileInput
import PIMRun
import PIMTrajectory
import validationPIM
import warnings
import os
import multiprocessing


warnings.filterwarnings('ignore')

def dataSearch():
    """
    This function searches for data to carry out the simulation inside the directory specified in the variablePIM.py file.

    Parameters: None.

    Return: A list of files to run.

    Raises: None.

    Example:

        filesToRun = dataSearch()
        print(filesToRun)
    """
    
    # Create an empty list to store the files to run
    filesToRun = []

    # List all files in the directory
    for file in variables.directorystr.iterdir():
        if file.is_file() and file.name.startswith("filesRun") and file.name.endswith(".txt"):
            with file.open() as readFile:
                lines = readFile.readlines()
                filesToRun.extend(lines)

    readFile = open(variables.directorystr.joinpath('filesRun'))
    filesToRun = readFile.readlines()
    readFile.close()
    print(filesToRun)
    return filesToRun

def integration(filesToRun):
    """
    Function integration takes in a list filesToRun and processes each line of the list that does not begin with # or a new line character. It removes the new line character from the end of each line and runs two simulation functions PIMR.PIMRun() and PIMT.PIMTrajectory() on each processed line.

    Parameters:

        filesToRun: a list of strings representing the files to be simulated.

    Returns: None

    Raises: None

    Example:

        files = ['# File names to run simulation\n', 'run1\n', 'run2\n', '\n']
        integration(files)
    """
    j=0
    for i,text in enumerate(filesToRun):
        if (text[0] != '#' and text[0] != '\n'):
            text = text[:-1]            # remove \n
            runInParallel(text)           # atmosphere (ground and then up to 1000 km altitude)
            PIMTrajectory.PIMTrajectory(text)    # space (from 1000 km altitude)

def continueIntegration ():
    """
    This function prompts the user to decide whether to proceed with the integration process or not. It will keep asking for input until the user enters either "yes" or "no".

    Parameters: This function doesn't take any parameters.

    Return: This function doesn't return anything.

    Raises: This function doesn't raise any exceptions.

    Example:

        Would you like to proceed with the integration? (yes/no) maybe
        Please, type yes or no
        Would you like to proceed with the integration? (yes/no) YES
    """
    while True:
        user_input = input('Would you like to proceed with the integration? (yes/no) ')

        if user_input.upper() == 'NO':
            print("Process closed. To proceed with the integration, just restart the program.")
            exit()
        elif user_input.upper() == 'YES':
            return
        else:
            print('Please, type yes or no')

def askForDir():
    """
    This function asks the user to input the name of a .txt file containing a list of meteors (directories) to be analyzed, 
    and a separator character between the name, date, and time of each meteor. It then reads the file, parses the data, and 
    returns a list of directories, a list of dates, and a list of options.

    Parameters: None

    Raises: None

    Returns:

        directoriesList: a list of directory names to be analyzed.
        dateList: a list of dates for each directory to be analyzed, where each date is a list containing integers for the year, month, day, hour, minute, and second.
        optionList: a list of integers representing options for each directory to be analyzed.

    Example:

        Insert the .txt file containing the list of meteors (directories) to be analyzed: meteors
        Insert the separator character between the name, data and horary: |
        ['meteor1', 'meteor2'], [[2022, 5, 1, 12, 0, 0], [2022, 5, 2, 18, 0, 0]], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    """
    directoriesFile = input("Insert the .txt file containing the list of meteors (directories) to be analyzed:  ")
    separator = input("Insert the separator character between the name, data and horary: ")
    data = validationPIM.fileToList(directoriesFile+'.txt')
    try:
        data = [i.split(separator) for i in data]
        directoriesList = [i[0] for i in data]
        dateList = [i[1].split('/')+i[2].split(':') for i in data]
        dateList = [[int(j) for j in i]for i in dateList]
        options = [i[3].split(':') for i in data]
        options = [[int(j) for j in i]for i in options]
        optionList = []
        [optionList.extend(i) for i in options]
    except:
        print("Error: unable to access meteor information. Please review the file. ")
        return
    print(directoriesList, dateList, optionList)
    return directoriesList, dateList, optionList
    
def verificationFiles(directoriesFile):
    
    filesRun = "filesRun.txt"
    
    with open(directoriesFile, "r") as f:
        nameDirs = f.read().splitlines()

    for nameDir in nameDirs:
        if not os.path.exists(nameDir) and os.path.isdir(nameDir):
            print(f"The directory '{nameDir}' doesn't exists. Please remove it from the list.")
            return False

        if not os.path.exists(os.path.join(os.getcwd(), nameDir, filesRun)):
            print(f"The file '{filesRun}' doesn't exists.")
            return False
            
        with open(filesRun, "r") as f:
            fileNames = f.read().splitlines()
            
        for fileName in fileNames:
            if not os.path.exists(fileName):
                print(f"The file '{fileName}' listed in '{filesRun}' of '{nameDir}' doesn't exist.")
                return False
    return True

def runInParallel(args_list):
    # Create a process pool
    pool = multiprocessing.Pool()

    # Use the pool's map method to apply the function to the arguments in parallel
    results = pool.map(PIMRun.PIMRun, args_list)

    # Close the pool after completion
    pool.close()
    pool.join()

    return results
##########################################################################################################

directoriesList,dateList,optionList = askForDir()

if verificationFiles == True:
    pass
else: 
    print("We haven't verified the existence of your initial files. We will create them from the .XML files.")
    createFileInput.multiCreate(directoriesList,dateList,optionList)

#continueIntegration ()

#filesToRun = dataSearch()

#integration(filesToRun)
 
