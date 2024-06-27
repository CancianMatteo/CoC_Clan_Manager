import os
from datetime import datetime
from time import sleep
from dotenv import load_dotenv
load_dotenv()
import requests
import gspread
from google.oauth2.service_account import Credentials
import random

def safe_execute(request):
    for n in range(0, 5):  # Retry up to 5 times
        try:
            return request()  # Attempt to execute the Google Sheets API request
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:  # Check if the error is due to rate limiting
                sleep_time = (2 ** n) + (random.randint(0, 1000) / 1000)  # Exponential backoff with jitter
                print(f"Rate limit exceeded, retrying in {sleep_time} seconds...")
                sleep(sleep_time)
            else:
                raise  # Re-raise the exception if it's not a rate limit error
    raise Exception("Failed to complete request after multiple retries.")


# Function to make an HTTP request to the API
def fetch_war_data_from_api(api_url, headers):
    response = requests.get(api_url+"/currentwar", headers)
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
            check_clan_members(api_url, headers)
            fetch_war_data_from_api(api_url, headers)
        elif api_data['state']=="notInWar":
            print("Nessuna war in corso, dormo 10h")
            return None
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep about 5 mins
        fetch_war_data_from_api(api_url, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")
    
# ---------------------------------------------------------------------------------------------------------------------------------
def fetch_members_data_from_api(api_url, headers):
    response = requests.get(api_url+"/members", headers)
    if response.status_code == 200:
        return response.json()
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep about 5 mins
        fetch_members_data_from_api(api_url, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")


# Functions to manipulate the JSON data as needed
def manipulate_data_members_list(member_list):
    manipulated_data = [[(member['tag'])[1:], member['name']] for member in member_list['items']]
    return manipulated_data 

# ---------------------------------------------------------------------------------------------------------------------------------
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
    manipulated_data = [(member['tag'][1:], member['name'], sumAttacksStarsOfAMember(member)) for member in (json_data['clan'])['members']]
    return manipulated_data 
    # Example: [('123456', 0.5), ('654321', 1), ('987654', 0)]


# Functions to upload data to Google Sheet
def get_Google_Sheets_file(sheet_key, credentials_path):
    # Use service account credentials to access Google Sheets APIv 
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
    gClient = gspread.authorize(credentials)
    # Open the Google Sheet by key
    sheets = gClient.open_by_key(sheet_key)
    return sheets

def check_that_all_sheets_have_same_members(sheet_key, credentials_path):
    sheets = get_Google_Sheets_file(sheet_key, credentials_path)
    previous_sheet_IDs = None
    for sheet in sheets:
        IDs = set(sheet.row_values(1)[1:])   # get the id (tag without #) of the members
        if previous_sheet_IDs is None:
            previous_sheet_IDs = IDs
        elif previous_sheet_IDs != IDs:
            raise Exception("The sheets have different members")

def update_members_to_google_sheet(sheet_key, credentials_path, clan_members_new_list):
    sheets = get_Google_Sheets_file(sheet_key, credentials_path)
    check_that_all_sheets_have_same_members(sheet_key, credentials_path)
    IDs = sheets.sheet1.row_values(1)[1:]   # get the id (tag without #) of the members
    for member in clan_members_new_list:
        if member[0] not in IDs:  # if the member is not in the sheet
            for sheet in sheets:    # add a column for the member to all the sheets
                new_member_col = sheet.col_count
                sheet.insert_cols(values=[[None]], col=new_member_col)
                sheet.update_cell(1, new_member_col, member[0])
                sheet.update_cell(2, new_member_col, member[1])
            print("Aggiunto: ")
            print(sheets.sheet1.col_values(new_member_col))
    for id in IDs:
        if id not in [member[0] for member in clan_members_new_list]:   # if the member is not in the clan any more
            ex_member_col = IDs.index(id)+2
            value = sheets.sheet1.cell(4, ex_member_col).value
            if value == None:
                value = 0
            else:
                value = float(value.replace(',', '.'))
            if value < 1:   # if the ex-member was not a valuable member
                print("Eliminazione: ")
                print(sheets.sheet1.col_values(ex_member_col))
                for sheet in sheets:
                    sheet.delete_columns(ex_member_col)        # delete the column of the ex-member
            else:
                print(f"Ex-member {sheets.sheet1.cell(2, ex_member_col).value} was a valuable member, so I keep his data")

# ---------------------------------------------------------------------------------------------------------------------------------               

def find_first_free_row(sheet):
    col_values = sheet.col_values(1)
    for i, value in enumerate(col_values):
        if not value:
            return i + 1
    return len(col_values) + 1

def upload_data_to_google_sheet(sheet_key, credentials_path, sheet_n:int, data):
    sheets = get_Google_Sheets_file(sheet_key, credentials_path)
    # Select which sheet of the file you want to work on
    sheet = sheets.get_worksheet(sheet_n)

    # Find the first free row and writes data in it
    row = find_first_free_row(sheet)
    sheet.update_cell(row, 1, datetime.now().strftime("%d/%m/%Y"))
    # Find members tag in the sheet
    IDs = sheet.row_values(1)[1:]   # get the id (tag without #) of the members
    for member in data:
        col = 1
        found = False
        for id in IDs:
            if id == member[0]: # if the member is already in the sheet
                sheet.update_cell(row, col, member[2])
                found = True
            col += 1
        if not found:
            col = sheet.col_count
            sheet.insert_cols(values=[], col=col)
            sheet.update_cell(1, col, member[0])
            sheet.update_cell(2, col, member[1])
            sheet.update_cell(row, col, member[2])
    tags = sheet.col_values(1)


# ___________________________________________________________________________________________________________________________________
def check_clan_members(coc_api_url, coc_api_headers):
    api_data = fetch_members_data_from_api(coc_api_url, coc_api_headers)
    print("API data: ")
    print(api_data)
    print("\n")
    clan_members_new_list = manipulate_data_members_list(api_data)
    print("Members list: ")
    print(clan_members_new_list)
    print("\n")
    update_members_to_google_sheet(sheet_key, credentials_path, clan_members_new_list)


# Main - Fetch data from CoC API
clan_id = os.environ.get('CLAN_ID')     #    hash character(#) -> URLencoded(%23)
api_url = "https://api.clashofclans.com/v1"
path_clan_info = f"/clans/{clan_id}"
request_headers = {
    'Authorization': f'Bearer {os.environ.get('COC_API_KEY')}',
    'Accept': 'application/json',
}
sheet_key = os.environ.get('SHEET_KEY')
credentials_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
while(True):
    check_clan_members(api_url+path_clan_info, request_headers)
    api_data = fetch_war_data_from_api(api_url+path_clan_info, request_headers)
    if api_data is not None:
        print("API data: ")
        print(api_data)
        # Manipulate the data: take the JSON and give an array of [(playerID: nOfStars)]
        manipulated_data = manipulate_data_current_war(api_data)
        print("\n\nDati manipolati: ")
        print(manipulated_data)
        # Upload data to Google Sheet
        upload_data_to_google_sheet(sheet_key, credentials_path, 0, manipulated_data)

    print("Nessuna war in corso, dormo 10h")
    sleep(36000) # sleep about 10h