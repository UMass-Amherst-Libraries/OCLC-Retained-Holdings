import requests
import pandas as pd
import dotenv
import os
import tkinter as tk
import sys

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
        self.filename = tk.filedialog.askopenfilename(filetypes =[('csv file', '*.csv')])
        self.selectedFile.config(text = f"Selected File: {self.filename[self.filename.rfind('/')+1:]}")
        self.selectedFile.update_idletasks()
        self.run.config(state="normal")

    def get_OCLC_retained_holdings(self):
        token = get_token()
        oclc_numbers = get_OCLC_numbers(self.filename)
        retained_holdings = get_retained_holdings(oclc_numbers, token)
        save_results(retained_holdings)
        PopupWindow("Results Saved!")


def get_token():
    resp = requests.post(os.getenv("TOKEN_URL"), 
                         auth=(os.getenv("WSKEY"), os.getenv("SECRET")), 
                         headers={'Content-Type': 'application/x-www-form-urlencoded'}, 
                         data={'grant_type': 'client_credentials', 'scope': os.getenv("SCOPE")})
    print(resp.status_code)
    return resp.json()['access_token']

def get_OCLC_numbers(filename):
    oclc_df = pd.read_csv(filename, dtype="string")
    if 'oclcNumber' not in oclc_df.columns:
        raise ValueError('CSV must have column oclcNumber')
    oclc_numbers = oclc_df['oclcNumber'].dropna().astype(str).tolist()
    return oclc_numbers

def get_retained_holdings(oclc_numbers, token):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    retained_holdings = []
    for i, ocn in enumerate(oclc_numbers, start=1):
        print(f'[{i}/{len(oclc_numbers)}] OCN {ocn} ...')
        if i%500 == 0 and i!=0:
            headers['Authorization'] = f'Bearer {get_token()}'
        r = requests.get(os.getenv("API_URL"), headers=headers, params={'oclcNumber': ocn})
        if r.status_code != 200:
            retained_holdings.append({'oclcNumber': ocn, 'title': '', 'allSymbols': '', 'allNames': '', 'notes': f'Error {r.status_code}'})
        data = r.json()
        brief_records = data.get('briefRecords', [])
        if not brief_records:
            retained_holdings.append({'oclcNumber': ocn, 'title': '', 'allSymbols': '', 'allNames': '', 'notes': 'No holdings'})
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
                retained_holdings.append({'oclcNumber': ocn, 'title': title, 'allSymbols': '|'.join(filter(None, symbols)), 'allNames': ' | '.join(filter(None, names))})
    return retained_holdings

def save_results(retained_holdings):
    out_df = pd.DataFrame(retained_holdings)
    out_name = 'retained_holdings_aggregated.csv'
    out_df.to_csv(out_name, index=False)
    out_df.head()

if __name__ == "__main__":
    dotenv.load_dotenv()
    Menu()
    #print(get_OCLC_numbers("test_file.csv"))
    #print(get_token())