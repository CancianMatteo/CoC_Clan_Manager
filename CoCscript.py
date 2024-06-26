import os
from datetime import datetime
from time import sleep
from dotenv import load_dotenv
load_dotenv()
import requests
import gspread
from google.oauth2.service_account import Credentials


# Function to make an HTTP request to the API
def fetch_data_from_api(api_url, headers):
    response = requests.get(api_url, headers)
    # Response Ok
    if response.status_code == 200:
        api_data =  response.json()
        if api_data['state']=="warEnded":
            return api_data
        elif(api_data['state']=="preparation" or api_data['state']=="inWar"):
            date_format = "%Y%m%dT%H%M%S.%fZ"
            secs_to_war_end = (datetime.strptime(api_data['endTime'], date_format) - datetime.now()).total_seconds()
            print("War in corso, dormo fino alla fine")
            sleep(secs_to_war_end+30) # sleep until war is ended
            fetch_data_from_api(api_url, headers)
        elif api_data['state']=="notInWar":
            print("Nessuna war in corso, dormo 10h")
            sleep(36000) # sleep about 10h
            fetch_data_from_api(api_url, headers)
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep about 5 mins
        fetch_data_from_api(api_url, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")


# Functions to manipulate the JSON data as needed
def manipulate_data_members_list(json_data):
    manipulated_data = [[item['tag'], item['name']] for item in json_data['items']]
    return manipulated_data 

def sumAttacksStarsOfAMember(member):
    try:   #try if the member has attacked
        sum = 0
        for attack in member['attacks']:
            sum += attack['stars']
    except KeyError:    # no attacks -> no stars
        return 0
    else:
        return sum/6    # return the number of stars divided by the maximum (6)

def manipulate_data_current_war(json_data):
    manipulated_data = [(member['tag'], member['name'], sumAttacksStarsOfAMember(member)) for member in (json_data['clan'])['members']]
    return manipulated_data 
    # Example: [('#123456', 0.5), ('#654321', 1), ('#987654', 0)]

def find_first_free_row(sheet):
    col_values = sheet.col_values(1)
    for i, value in enumerate(col_values):
        if not value:
            return i + 1
    return len(col_values) + 1

# Function to upload data to Google Sheet
def upload_to_google_sheet(data, sheet_key, credentials_path):
    # Use service account credentials to access Google Sheets APIv 
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
    gClient = gspread.authorize(credentials)
    # Open the Google Sheet by key
    sheets = gClient.open_by_key(sheet_key)
    # Select which sheet of the file you want to work on
    sheet1 = sheets.sheet1

    # Find the first free row and writes data in it
    row = find_first_free_row(sheet1)
    sheet1.update_cell(row, 1, datetime.now().strftime("%d/%m/%Y"))
    # Find members tag in the sheet
    IDs = sheet1.row_values(1)
    for member in data:
        tag = member[0][1:] # get the tag without the hash character
        col = 1
        found = False
        for id in IDs:
            if id == tag:
                sheet1.update_cell(row, col, member[2])
                found = True
            col += 1
        if not found:
            col = sheet1.col_count
            sheet1.insert_cols([[None]], col)
            sheet1.update_cell(1, col, tag)
            sheet1.update_cell(2, col, member[1])
            sheet1.update_cell(row, col, member[2])
    tags = sheet1.col_values(1)

#Main
# Fetch data from CoC API
clan_id = os.environ.get('CLAN_ID')     #    hash character(#) -> URLencoded(%23)
api_url = "https://api.clashofclans.com/v1"
path_members_list = f"/clans/{clan_id}/members"
path_current_war = f"/clans/{clan_id}/currentwar"
latest_ended_war_endtime = "20240208T182643.000Z"
request_headers = {
    'Authorization': f'Bearer {os.environ.get('COC_API_KEY')}',
    'Accept': 'application/json',
}
while(True):
    api_data = fetch_data_from_api(api_url+path_current_war, request_headers)
    print("API data: ")
    print(api_data)

    # Manipulate the data: take the JSON and give an array of [(playerID: nOfStars)]
    manipulated_data = manipulate_data_current_war(api_data)
    print("\n\nDati manipolati: ")
    print(manipulated_data)

    # Upload data to Google Sheet
    sheet_key = os.environ.get('SHEET_KEY')
    credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
    upload_to_google_sheet(manipulated_data, sheet_key, credentials_path)

    print("Nessuna war in corso, dormo 10h")
    sleep(36000) # sleep about 10h