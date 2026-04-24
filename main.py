import requests
import pandas as pd
import dotenv
import os
import tkinter as tk
from tkinter import filedialog
import sys
import aiohttp
import asyncio
from tqdm import tqdm 
import logging
from datetime import datetime

# Popup Windows to give alert notices
class PopupWindow:
    def __init__(self, text):
        self.popup = tk.Tk()
        self.popup.wm_title("Popup Notice")
        self.popup.columnconfigure(0, minsize=100)
        self.popup.rowconfigure([0, 1], minsize=25)


        self.text_label = tk.Label(master=self.popup, text=text)
        self.text_label.grid(row=0, column=0)
        self.close_button = tk.Button(master=self.popup, text="OK", command=self.close)
        self.close_button.grid(row=1, column=0)

        self.popup.mainloop()

    def close(self):
        self.popup.destroy()

class Menu:
    def __init__(self):
        self.act_menu = tk.Tk()
        self.act_menu.wm_title("Get OCLC Retained Holdings")

    # File Select Button
        self.select = tk.Button(master=self.act_menu, text="Select .csv file", command=self.file_select, font='TkDefaultFont 10')
        #self.run.grid(row=4, column=1, columnspan=1)
        self.select.pack(side='top')

    # Selected File Name
        self.selectedFile = tk.Label(master=self.act_menu, text="Selected File: ", font='TkDefaultFont 10')
        self.selectedFile.pack(side='top')

    # Get OCLC Retained Holdings Button
        self.run = tk.Button(master=self.act_menu, text="Retrieve and Save OCLC Retained Holdings", command=self.get_OCLC_retained_holdings, font='TkDefaultFont 10', state="disabled")
        #self.run.grid(row=4, column=1, columnspan=1)
        self.run.pack(side='top', pady=10)
        self.filename = ''

    # Menu Bar
        # File>Exit and File>Reconfigure
        self.main_menu_bar = tk.Menu(master=self.act_menu)
        self.file_menu = tk.Menu(master=self.main_menu_bar, tearoff=0)
        self.file_menu.add_command(label="Exit", command=sys.exit)
        self.main_menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.act_menu.config(menu=self.main_menu_bar)
        self.act_menu.update_idletasks()
        
        self.act_menu.mainloop()

    def file_select(self):
        logging.info("File select clicked")
        self.filename = filedialog.askopenfilename()
        self.selectedFile.config(text = f"Selected File: {self.filename[self.filename.rfind('/')+1:]}")
        self.selectedFile.update_idletasks()
        self.run.config(state="normal")

    def get_OCLC_retained_holdings(self):
        logging.info("Get OCLC Retained Holdings clicked")
        oclc_numbers = readInputFile(self.filename)
        chunked_oclc_numbers = chunkList(oclc_numbers)

        retained_holdings = []
        for i, chunk in enumerate(chunked_oclc_numbers, start=1):
            logging.info(f'Retrieving retained holdings for chunk {i}')
            chunk_retained_holdings = asyncio.run(asyncGetRetainedHoldings(chunk))
            retained_holdings += chunk_retained_holdings
        saveResults(retained_holdings, self.filename)

def getToken():
    logging.info("Getting access token...")
    resp = requests.post(os.getenv("TOKEN_URL"), 
                         auth=(os.getenv("WSKEY"), os.getenv("SECRET")), 
                         headers={'Content-Type': 'application/x-www-form-urlencoded'}, 
                         data={'grant_type': 'client_credentials', 'scope': os.getenv("SCOPE")},
                         timeout=1000)
    logging.info("Access token retrieved")
    return resp.json()['access_token']

def readInputFile(filename):
    logging.info(f"Reading input file: {filename}")
    if filename[filename.rfind('.'):] == '.csv':
        oclc_df = pd.read_csv(filename, dtype="string")
        if 'oclcNumber' not in oclc_df.columns:
            logging.warning('CSV must have column named oclcNumber.')
            raise ValueError('CSV must have column named oclcNumber.')
    elif filename[filename.rfind('.'):] == '.tsv':
        oclc_df = pd.read_csv(filename, dtype="string", delimiter = '\t')
        if 'oclcNumber' not in oclc_df.columns:
            logging.warning('CSV must have column named oclcNumber.')
            raise ValueError('CSV must have column oclcNumber.')
    else:
        PopupWindow("File type must be .csv or .tsv")

    oclc_numbers = oclc_df['oclcNumber'].dropna().astype(str).tolist()
    logging.info("Reading successful, OCLC numbers retrieved.")
    return oclc_numbers

def chunkList(oclc_numbers):
    chunk_size = 10000
    logging.info(f"Splitting list of OCLC numbers into chunks of {chunk_size} numbers.")
    split_list = []
    for i in range(0, len(oclc_numbers), chunk_size):
        split_list.append(oclc_numbers[i:i+chunk_size])
    logging.info(f"List split into {len(split_list)} chunks.")
    return split_list

async def asyncGetRetainedHoldings(oclc_numbers):
    async_conn = aiohttp.TCPConnector(limit=100) # defines the number of threads to use
    async_time = aiohttp.ClientTimeout(total=100000)
    
    url = os.getenv("API_URL")
    
    headers = {'Authorization': f'Bearer {getToken()}', 'Accept': 'application/json'}
    
    tasks = []
    async with aiohttp.ClientSession(connector=async_conn, timeout=async_time) as session:
        for ocn in oclc_numbers:
            params={'oclcNumber': ocn}
            tasks.append(asyncio.create_task(asyncRequest(session=session, url=url, headers=headers, params=params)))
        retained_holdings = [await f for f in tqdm(asyncio.as_completed(tasks), total=len(tasks))]
    return retained_holdings

async def asyncRequest(session, url, headers, params):
    response = await session.get(url=url, headers=headers, params=params)
    data = processResponse(response, params)
    return await data

async def processResponse(response, params):
    if response.status != 200:
        logging.warning(f'Request on {params["oclcNumber"]} returned {response.status}')
        data = {'oclcNumber': params["oclcNumber"], 'title': '', 'allSymbols': '', 'allNames': '', 'notes': f'Error {response.status}'}
    else:
        data = await response.json()
        brief_records = data.get('briefRecords', [])
        if not brief_records:
            data = {'oclcNumber': params['oclcNumber'], 'title': '', 'allSymbols': '', 'allNames': '', 'notes': 'No holdings'}
        else:
            title = brief_records[0].get('title', '')
            symbols = []
            names = []
            for br in brief_records:
                inst = br.get('institutionHolding', {})
                if isinstance(inst, dict):
                    for ih in inst.get('briefHoldings', []):
                        symbols.append(ih.get('oclcSymbol', ''))
                        names.append(ih.get('insitutionName'))
                elif isinstance(inst, list):
                    for ih in inst:
                        symbols.append(ih.get('oclcSymbol', ih.get('symbol', '')))
                        names.append(ih.get('institutionName', ih.get('name', '')))
                data = {'oclcNumber': params['oclcNumber'], 'title': title, 'allSymbols': '|'.join(filter(None, symbols)), 'allNames': ' | '.join(filter(None, names))}
    return data


def saveResults(retained_holdings, input_file_name):
    out_name = f"Output/Retained Holdings - {input_file_name[input_file_name.rfind('/')+1:input_file_name.rfind('.')]}.csv"
    logging.info(f"Saving results to {out_name}")
    out_df = pd.DataFrame(retained_holdings)
    out_df.to_csv(out_name, index=False)
    out_df.head()
    logging.info("Results saved!")
    PopupWindow("Results Saved!")

if __name__ == "__main__":
    dotenv.load_dotenv()

    try:
        os.mkdir(os.getenv('LOG_PATH'))
        print(f"Directory for logs \"{os.getenv('LOG_PATH')}\" created")
    except Exception as e:
        print("Existing log directory found")

    start_time = datetime.now()
    logFile = f'{os.getenv("LOG_PATH")}/OCLC Retained Holdings - {start_time.year}-{start_time.month}-{start_time.day}--{start_time.hour}-{start_time.minute}-{start_time.second}.log'
    logging.basicConfig(filename=logFile, encoding='utf-8', level=logging.DEBUG,
                    format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    logging.info("Beginning Log")

    Menu()
