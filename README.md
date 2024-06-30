# CoC_Clan_Manager
Python script that interact with Clash of Clans API to fetch data, manipulates them and put the results on a easily readable Google Sheets, to make statistics of members performance

## Features
- Script-based management of clan activities to automate the population of a Google Sheets.
- Automatic tracking of member attacks, performance and activity
- Integration with CoC API for real-time data updates
- User-friendly command-line interface

## Installation
1. Clone the repository: `git clone https://github.com/your-username/CoC-script-clan-manager.git`.
2. Install the required dependencies, in terminal run: `pip install dotenv requests gspread google`.
3. Create a Google Cloud account and register the API, create a Sheets and give write access to the email of the Google API.
4. Configure the project by editing the `.env` and `YOUR_GOOGLE_CREDENTIALS.json` files (as in the examples).
5. Run the script: `CoCscript.py`

## Usage
1. Open your terminal and navigate to the project directory.
2. Run the script: `CoCscript.py`

## Contributing
Contributions are welcome! If you have any ideas or improvements, feel free to open an issue or submit a pull request.
