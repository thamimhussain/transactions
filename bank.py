from sqlite3 import Error
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from openai import OpenAI

import pdfplumber
import time
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'TransactionStatements'

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key = api_key)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods = ['POST'])
def upload_file():
    if request.method == 'POST':

        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})

        bank = request.form['bank']
        file = request.files['file']

        file.save('TransactionStatements/' + file.filename)

        extracted_text = extract_text_from_pdf('TransactionStatements/'+file.filename)

        if bank == "Bank of America":
            categories, dates, prices = extract_purchases_bofa(extracted_text)
        elif bank == "Chase":
            categories, dates, prices = extract_purchases_chase(extracted_text)

        print("Starting categorization")
        categories = createCategory(categories)
        print("Categorized! GPT is done")

        connection = connectDb('transactions.db')
        
        transaction_table = """
        CREATE TABLE IF NOT EXISTS transactions(
            Date TEXT,
            Category TEXT,
            Price TEXT
        );
        """
        executeQuery(connection, transaction_table)

        # print(len(categories))
        cursor = connection.cursor()
        for transaction in range(len(categories)):

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE Date = ? AND Category = ? AND Price = ?",
                           (dates[transaction], categories[transaction].content, prices[transaction]))
            existing_count = cursor.fetchone()[0]

            if existing_count == 0:
                add_transaction = """
                    INSERT INTO transactions (Date, Category, Price)
                    VALUES (?, ?, ?)
                """
                cursor.execute(add_transaction, (dates[transaction], categories[transaction].content, prices[transaction]))

        # print("completed for loop")


        connection.commit()

        
        df = pd.read_sql_query('SELECT * FROM transactions', connection)
        print("read sql table")
        connection.close()

        excel_file = 'transactions_data.xlsx'
        print("starting excel transfer")
        df.to_excel(excel_file, index=False)
        print("finish excel transfer")
        
        return jsonify({'message': 'File uploaded successfully'})


#Extract text from the image
def extract_text_from_pdf(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[2]
    text = page.extract_text()
    return text

#Use Chat GPT to categorize transacitons
def categorize_transaction(transaction_description):
    prompt = f"Categorize the transaction: {transaction_description}. Use one of the following words and make sure to give only one word: Dining, Clothes, Groceries, Rent, Transportation, Entertainment, Health, Miscellaneous"
    chat_completion = client.chat.completions.create(
        messages = [
            {"role": "system", "content": "You are assisting in categorizing transactions, using your knowledge to suggest appropriate categories based on transaction details."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-4o"
    )
    return chat_completion.choices[0].message

#Create the category
def createCategory(extractedTransactions):
    for index, transaction in enumerate(extractedTransactions):
        category = categorize_transaction(transaction)
        extractedTransactions[index] = category
        time.sleep(2)
    return extractedTransactions

#Format text from the Bank of America statements
def extract_purchases_bofa(text):
    start_index = text.find("Purchases and Adjustments") + len("Purchases and Adjustments")
    end_index = text.find("TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD")

    purchases_and_adjustments_section = text[start_index:end_index].strip()

    lines = purchases_and_adjustments_section.split('\n')

    extracted_transactions = []
    extracted_dates = []
    extracted_prices = []

    for line in lines:
        parts = line.split(' ', 2)
        dateText = parts[0]
        transactionText = ' '.join(parts[-1].split()[:-3])
        transactionText = transactionText.replace('=', '')
        priceText = parts[-1].split()[-1]

        extracted_dates.append(dateText)
        extracted_transactions.append(transactionText)
        extracted_prices.append(priceText)

    for i, input in enumerate(extracted_transactions):
        words = input.split()
        result = ' '.join(words[:-2])
        extracted_transactions[i] = result

    return extracted_transactions, extracted_dates, extracted_prices

#Format text from the Chase statements
def extract_purchases_chase(text):
    arrayText = text.split('\n')
    joinArray = '|'.join(arrayText)
    finalArray = joinArray.split('||')
    for index in range(len(finalArray)):
        finalArray[index] = finalArray[index].split('|')


    extracted_transactions = []
    extracted_dates = []
    extracted_prices = []

    for i in range(3):
        for input in finalArray[i]:
            if i == 0:
                extracted_dates.append(input)
            elif i == 1:
                words = input.split()
                result = ' '.join(words[:-2])
                extracted_transactions.append(result)
            elif i == 2:
                extracted_prices.append(input)
    
    return extracted_transactions, extracted_dates, extracted_prices

def connectDb(path):
    connection = None
    try:
        connection = sqlite3.connect(path)
        print("Success")
    except Error as e:
        print("The issue {e} has occurred.")
    return connection

def executeQuery(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        print("Success")
    except Error as e:
        print("The issue {e} has occurred.")


if __name__ == '__main__':
    app.run(debug=True)
