import os
from datetime import datetime
from time import sleep
from dotenv import load_dotenv
load_dotenv()
import requests
import gspread
from google.oauth2.service_account import Credentials


# Functions to make an HTTP request to the API
def fetch_members_data_from_api(api_clan_url, headers):
    response = requests.get(api_clan_url+"/members", headers)
    if response.status_code == 200:
        return response.json()
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep about 5 mins
        fetch_members_data_from_api(api_clan_url, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")
    
# ---------------------------------------------------------------------------------------------------------------------------------
def fetch_war_data_from_api(api_clan_url, headers):
    response = requests.get(api_clan_url+"/currentwar", headers)
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
            check_clan_members(api_clan_url, headers)
            fetch_war_data_from_api(api_clan_url, headers)
        elif api_data['state']=="notInWar":
            return None
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep about 5 mins
        fetch_war_data_from_api(api_clan_url, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")

# ---------------------------------------------------------------------------------------------------------------------------------
def fetch_warleague_wartags_data_from_api(api_url, path_clan_info, headers):
    response = requests.get(api_url+path_clan_info+"/currentwar/leaguegroup", headers)
    if response.status_code == 200:
        api_data =  response.json()
        if api_data['state']=="warEnded":   #war ended, we can fetch the results
            war_tags = api_data["rounds"]["warTags"]
            CWL_rounds = []
            for war_tag in war_tags:
                CWL_rounds.append(fetch_warleague_results_from_api(api_url+"/clanwarleagues/wars/", war_tag, headers))
            return CWL_rounds   # IDEAL END
        elif(api_data['state']=="preparation" or api_data['state']=="inWar"): #war ongoing, we need to wait
            date_format = "%Y%m%dT%H%M%S.%fZ"
            secs_to_war_end = (datetime.now().replace(day=10) - datetime.now()).total_seconds()
            print("War in corso, dormo fino alla fine")
            sleep(secs_to_war_end+300) # sleep until war is ended
            requests.get(api_url+path_clan_info+"/currentwar/leaguegroup", headers)
            api_data =  response.json()
            if(api_data['state']=="preparation" or api_data['state']=="inWar"):
                last_war_tag = api_data["rounds"]["warTags"][-1]
                response = requests.get(api_url+"/clanwarleagues/wars/"+last_war_tag, headers)
                api_data =  response.json()
                secs_to_war_end = (datetime.strptime(api_data['endTime'], date_format) - datetime.now()).total_seconds()
                print("Ultima war in corso, dormo fino alla fine")
                sleep(secs_to_war_end+30) # sleep until war is ended
            check_clan_members(api_url+path_clan_info, headers)
            fetch_warleague_wartags_data_from_api(api_url, path_clan_info, headers)

    elif response.status_code == 404: 
        print("Non ci sono Clan War League in corso, controllo la war normale")
        return None
    # Error 5**: server side error
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep 5 mins
        fetch_warleague_wartags_data_from_api(api_url, path_clan_info, headers)
    # Other error
    else:
        raise Exception(f"Failed to fetch data from API. Status code: {response.status_code}. Response: {response.text}")

def fetch_warleague_results_from_api(api_wars_url, war_tag, headers):
    response = requests.get(api_wars_url+war_tag, headers)
    if response.status_code == 200:
        api_data =  response.json()
        return api_data
    elif response.status_code/100 == 5: 
        print("Il server di CoC ha qualche problema, riprovo tra 5 min")
        sleep(300) # sleep 5 mins
        fetch_warleague_results_from_api(api_url+"/clanwarleagues/wars/", war_tag, headers)


# Functions to manipulate the JSON data as needed
def manipulate_data_members_list(member_list):
    manipulated_data = [[(member['tag'])[1:], member['name']] for member in member_list['items']]
    return manipulated_data 

# ---------------------------------------------------------------------------------------------------------------------------------
def sumAttacksStarsOfAMember(member, max_attacks=2):
    max_stars = max_attacks*3
    try:   #try if the member has attacked
        sum = 0
        for attack in member['attacks']:
            sum += attack['stars']
    except KeyError:    # no attacks -> no stars
        return 0
    else:
        return "="+str(sum)+"/"+str(max_stars)   # return the number of stars divided by the maximum (6)

def manipulate_data_current_war(json_data):
    members_stars = {}
    for member in json_data['clan']['members']:
        tag = member['tag'][1:]
        members_stars[tag] = 0
        try:   #try if the member has attacked
            members_stars[tag] += member["attacks"][0]["stars"]
            members_stars[tag] += member["attacks"][1]["stars"]
        except KeyError:    # no attacks -> no stars
            pass
    for member in members_stars:
        members_stars[member] = "="+str(members_stars[member])+"/"+str(2*3)
    return members_stars
    # Example: {'123456': "=3/6", '654321': "=6/6", '987654': "=0/6"}
# ---------------------------------------------------------------------------------------------------------------------------------
def manipulate_data_cwl_rounds(rounds_data):
    members_stars = {}
    members_attacks_doable = {}
    members_attacks_done = {}
    for round in rounds_data:
        for member in round['clan']['members']:
            tag = member['tag'][1:]
            if members_attacks_doable.get(tag, None) == None:
                members_stars[tag] = 0
                members_attacks_done[tag] = 0
                members_attacks_doable[tag] = 0
            try:   #try if the member has attacked
                stars = member["attacks"][0]["stars"]
            except KeyError:    # no attacks -> no stars
                stars = -1
            if stars != -1:
                members_stars[tag] += stars
                members_attacks_done[tag] += 1
            members_attacks_doable[tag] += 1
    for member in members_attacks_doable:
        members_stars[member] = "="+str(members_stars[member])+"/"+str(members_attacks_doable[member]*3)
        members_attacks_done[member] = "="+str(members_attacks_done[member])+"/"+str(members_attacks_doable[member])
    return members_stars, members_attacks_done
    # Example: {'123456': "=14/21", '654321': "=18/21", '987654': "=11/15"}, {'123456': "=6/7", '654321': "=7/7", '987654': "=4/5"}


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
    i=1
    for sheet in sheets:
        IDs = set(sheet.row_values(1)[1:])   # get the id (tag without #) of the members
        if previous_sheet_IDs is None:
            previous_sheet_IDs = IDs
        elif previous_sheet_IDs != IDs:
            missing_prev = IDs.difference(previous_sheet_IDs)
            missing_now = previous_sheet_IDs.difference(IDs)
            raise Exception("The sheets("+str(i-1)+"-"+str(i)+") have different members:\n"+str(missing_prev)+" and "+str(missing_now))
        i+=1

def update_members_to_google_sheet(sheet_key, credentials_path, clan_members_new_list):
    sheets = get_Google_Sheets_file(sheet_key, credentials_path)
    check_that_all_sheets_have_same_members(sheet_key, credentials_path)
    sheet1_IDs = sheets.sheet1.row_values(1)[1:]   # get the id (tag without #) of the members
    for member in clan_members_new_list:
        if member[0] not in sheet1_IDs:  # if the member is not in the sheet
            for sheet in sheets:    # add a column for the member to all the sheets
                new_member_col = sheet.col_count
                sheet.insert_cols(values=[[None]], col=new_member_col)
                sheet.update_cell(1, new_member_col, member[0])
                sheet.update_cell(2, new_member_col, member[1])
            print("Aggiunto: ")
            print(sheets.sheet1.col_values(new_member_col))
    for id in sheet1_IDs:
        if id not in [member[0] for member in clan_members_new_list]:   # if the member is not in the clan any more
            ex_member_col = sheet1_IDs.index(id)+2
            value = sheets.sheet1.cell(4, ex_member_col).value
            if value == None:
                value = 0
            else:
                value = float(value.replace(',', '.'))
            if value < 1:   # if the ex-member was not a valuable member
                print("Eliminazione: ")
                print(sheets.sheet1.col_values(ex_member_col))    
                for sheet in sheets:    # delete the column of the ex-member in the sheets
                    IDs = sheet.row_values(1)[1:]   # get the id (tag without #) of the members
                    ex_member_col = IDs.index(id)+2
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
    sheet_IDs = sheet.row_values(1)[1:]   # get the id (tag without #) of the members
    for member in data:
        col = 2
        found = False
        for sheet_id in sheet_IDs:
            if sheet_id == member[0]: # if the member is already in the sheet
                found = True
                break
            col += 1
        if not found:
            new_member_col = sheet.col_count
            for s in sheets:    # add a column for the member to all the sheets
                s.insert_cols(values=[[None]], col=new_member_col)
                s.update_cell(1, new_member_col, member[0])
                s.update_cell(2, new_member_col, member[1])
            print("Aggiunto probabile ex-membro: ")
            print(sheet.col_values(new_member_col))
        sheet.update_cell(row, col, member[2])


def upload_war_data_to_google_sheet(sheet_key, credentials_path, data):
    upload_data_to_google_sheet(sheet_key, credentials_path, 0, data)


def upload_cwl_data_to_google_sheet(sheet_key, credentials_path, manipulated_stars_data, manipulated_partecipation_data):
    upload_data_to_google_sheet(sheet_key, credentials_path, 1, manipulated_stars_data)
    upload_data_to_google_sheet(sheet_key, credentials_path, 2, manipulated_partecipation_data)

# ___________________________________________________________________________________________________________________________________
def check_clan_members(coc_api_url, coc_api_headers):
    api_data = fetch_members_data_from_api(coc_api_url, coc_api_headers)
    print("\n")
    clan_members_new_list = manipulate_data_members_list(api_data)
    print("Members list: ")
    print(clan_members_new_list)
    print("\n")
    update_members_to_google_sheet(sheet_key, credentials_path, clan_members_new_list)


# Main - Fetch data from CoC API
clan_id = "%23" + os.environ.get('CLAN_ID')[1:]     #    hash character(#) -> URLencoded(%23)
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
    api_data = fetch_warleague_wartags_data_from_api(api_url, path_clan_info, request_headers)
    if api_data is not None:
        print("API data: ")
        print(api_data)
        # Manipulate the data: take the JSON and give two associative array: {playerID: nStars/TOT}, {playerID: nAttacks/TOT}
        manipulated_stars_data, manipulated_partecipation_data = manipulate_data_cwl_rounds(api_data)
        print("\n\nDati manipolati: ")
        print(manipulated_stars_data, manipulated_partecipation_data)
        # Upload cwl data to Google Sheet
        upload_cwl_data_to_google_sheet(sheet_key, credentials_path, manipulated_stars_data, manipulated_partecipation_data)
    else:
        api_data = fetch_war_data_from_api(api_url+path_clan_info, request_headers)
        if api_data is not None:
            print("API data: ")
            print(api_data)
            # Manipulate the data: take the JSON and give an array of [(playerID, nStars)]
            manipulated_data = manipulate_data_current_war(api_data)
            print("\n\nDati manipolati: ")
            print(manipulated_data)
            # Upload war data to Google Sheet
            upload_war_data_to_google_sheet(sheet_key, credentials_path, 0, manipulated_data)
        else:
            print("Il server non mi ha restituito nessun dato")

    print("Nessuna war in corso, dormo 10h")
    sleep(36000) # sleep about 10h