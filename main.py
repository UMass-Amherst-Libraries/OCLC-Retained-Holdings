import requests
import pandas as pd
import dotenv
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import sv_ttk
import sys
import aiohttp
import asyncio
from tqdm import tqdm 
import logging
from datetime import datetime
import numpy as np

# Popup Windows to give alert notices
class PopupWindow:
    def __init__(self, text):
        self.popup = tk.Tk()
        self.popup.attributes("-topmost", True)
        self.popup.wm_title("Popup Notice")
        self.popup.columnconfigure(0, minsize=100)
        self.popup.rowconfigure([0, 1], minsize=25)


        self.text_label = ttk.Label(master=self.popup, text=text)
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

        self.act_menu.configure(background="lavender")
        sv_ttk.set_theme("light")

    # File Select Button
        self.select = tk.Button(master=self.act_menu, text="Select .csv file", command=self.file_select, font='TkDefaultFont 10')
        #self.run.grid(row=4, column=1, columnspan=1)
        self.select.pack(side='top', pady=5)

    # Selected File Name
        self.selectedFile = ttk.Label(master=self.act_menu, text="No file selected", font='TkDefaultFont 10')
        self.selectedFile.configure(background="lavender")
        self.selectedFile.pack(side='top', pady=5, padx=10)

    # Get OCLC Retained Holdings Button
        self.run = tk.Button(master=self.act_menu, text="Retrieve and Save OCLC Retained Holdings", command=self.get_OCLC_retained_holdings, font='TkDefaultFont 10 bold', state="disabled")
        #self.run.grid(row=4, column=1, columnspan=1)
        self.run.pack(side='top', padx=10, pady=5)
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
        if self.filename =='':
            self.selectedFile.config(text = f"No file selected")
            self.run.config(state="disabled")
        else:
            self.selectedFile.config(text = f"Selected File: {self.filename[self.filename.rfind('/')+1:]}")
            self.run.config(state="normal")
        self.selectedFile.update_idletasks()

    def get_OCLC_retained_holdings(self):
        logging.info("Get OCLC Retained Holdings clicked")
        oclc_numbers = readInputFile(self.filename)
        chunked_oclc_numbers = chunkList(oclc_numbers)

        for (i, chunk) in chunked_oclc_numbers:
            logging.info(f'Retrieving retained holdings for chunk {i}')

            oclc_df = pd.DataFrame(columns=['oclcNumber','title', 'allSymbols', 'Non-UM holdings count', 'UM held', 'allNames', 'notes'], index=range(0,len(chunk.index)), data=[]*100)
            
            chunk_retained_holdings = asyncio.run(asyncGetRetainedHoldings(chunk))
            for index, row in enumerate(chunk_retained_holdings):
                oclc_df.iloc[index] = pd.Series(row)
            chunk = pd.merge(chunk,oclc_df,on='oclcNumber', how='inner')
            if i==0:
                chunks = [chunk]
            else:
                chunks.append(chunk)
        retained_holdings = pd.concat(chunks)
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
            PopupWindow('CSV must have column named oclcNumber.')
    elif filename[filename.rfind('.'):] == '.tsv':
        oclc_df = pd.read_csv(filename, dtype="string", delimiter = '\t')
        if 'oclcNumber' not in oclc_df.columns:
            logging.warning('CSV must have column named oclcNumber.')
            PopupWindow('CSV must have column oclcNumber.')
    else:
        PopupWindow("File type must be .csv or .tsv")
    
    #oclc_numbers = oclc_df['oclcNumber'].dropna().astype(str).tolist()
    logging.info("Reading successful, OCLC numbers retrieved.")
    return oclc_df

def chunkList(oclc_numbers):
    chunk_size = 1000
    logging.info(f"Splitting list of OCLC numbers into chunks of {chunk_size} numbers.")
    
    split_dfs = oclc_numbers.groupby(np.arange(len(oclc_numbers.index))//chunk_size)

    logging.info(f"List split into {split_dfs.ngroups} chunks.")
    return split_dfs

async def asyncGetRetainedHoldings(oclc_numbers:pd.DataFrame):
    async_conn = aiohttp.TCPConnector(limit=100) # defines the number of threads to use
    async_time = aiohttp.ClientTimeout(total=100000)
    
    url = os.getenv("API_URL")
    
    headers = {'Authorization': f'Bearer {getToken()}', 'Accept': 'application/json'}
    
    tasks = []
    session = aiohttp.ClientSession(connector=async_conn, timeout=async_time)
    for row in oclc_numbers.index:
        if pd.isna(oclc_numbers.loc[row]['oclcNumber']):
            continue
        else:
            params={'oclcNumber': oclc_numbers.loc[row]['oclcNumber']}
            tasks.append(asyncio.create_task(asyncRequest(session=session, url=url, headers=headers, params=params)))
    retained_holdings = [await f for f in tqdm(asyncio.as_completed(tasks), total=len(tasks))]
    await session.close()
    return retained_holdings

async def asyncRequest(session, url, headers, params):
    response = await session.get(url=url, headers=headers, params=params)
    data = processResponse(response, params)
    return await data

async def processResponse(response, params):
    if response.status != 200:
        logging.warning(f'Request on {params["oclcNumber"]} returned {response.status}')
        data = {'oclcNumber': params["oclcNumber"], 'title': '', 'allSymbols': '', 'Non-UM holdings count': '', 'UM held': '', 'allNames': '', 'notes': f'Error {response.status}'}
    else:
        data = await response.json()
        brief_records = data.get('briefRecords', [])
        if not brief_records:
            data = {'oclcNumber': params['oclcNumber'], 'title': '', 'allSymbols': '', 'Non-UM holdings count': '', 'UM held': '', 'allNames': '', 'notes': 'No holdings'}
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
                nonNoneSymbols = [x for x in symbols if x is not None]
                nonUmassSymbols = [x for x in nonNoneSymbols if x !="AUM"]
                data = {'oclcNumber': params['oclcNumber'], 'title': title, 'allSymbols': '|'.join(nonNoneSymbols), 'Non-UM holdings count': str(len(nonUmassSymbols)), 'UM held': str(nonUmassSymbols!=nonNoneSymbols), 'allNames': ' | '.join(filter(None, names)), 'notes': ''}
    return data


def saveResults(out_df, input_file_name):
    out_name = f"Output/Retained Holdings - {input_file_name[input_file_name.rfind('/')+1:input_file_name.rfind('.')]}.csv"
    logging.info(f"Saving results to {out_name}")
    out_df.drop_duplicates().to_csv(out_name, index=False)
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
