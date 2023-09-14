import os
from flask import Flask, render_template, request, redirect, url_for, abort
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime
import json
import eml_parser
from msg_parser import MsOxMessage
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask import jsonify
import hashlib



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///{}'.format(os.path.join(os.getcwd(), 'database.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.eml', '.msg']

class Mail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fromMailAddress = db.Column(db.Text, index=True)
    toMailAddress = db.Column(db.Text, index=True)
    ccMailAddress = db.Column(db.Text)
    date = db.Column(db.Text, index=True)
    subject = db.Column(db.Text, index=True)
    receivedIP = db.Column(db.Text)
    uriMail = db.Column(db.Text)
    spf = db.Column(db.Text)
    returnPath = db.Column(db.Text)
    dkimMail = db.Column(db.Text)
    attachments = db.Column(db.Text)
    attachmentHash = db.Column(db.String(32))

    def to_dict(self):
        return {
            'id': self.id,
            'fromMailAddress': self.fromMailAddress,
            'toMailAddress': self.toMailAddress,
            'ccMailAddress': self.ccMailAddress,
            'date': self.date,
            'subject': self.subject,
            'receivedIP': self.receivedIP,
            'uriMail': self.uriMail,
            'spf': self.spf,
            'returnPath': self.returnPath,
            'dkimMail': self.dkimMail,
            'attachments': self.attachments,
            'attachmentHash': self.attachmentHash
        }
def calculate_hash(file_content):
    hash_object = hashlib.md5()
    hash_object.update(file_content)
    return hash_object.hexdigest()

with app.app_context():
    db.create_all()

def json_serial(obj):
  if isinstance(obj, datetime):
      serial = obj.isoformat()
      return serial

#Rotating Table Page
@app.route('/table')
def table():
    return render_template('table.html')
@app.route('/get_mails', methods=['POST'])
def get_mails():
    page = request.args.get('page', 1, type=int)
    from_address = request.json.get('from_address')
    to_address = request.json.get('to_address')
    cc_address = request.json.get('cc_address')
    subject = request.json.get('subject')
    spf = request.json.get('spf')
    received_ip = request.json.get('received_ip')
    uri_mail = request.json.get('uri_mail')
    return_path = request.json.get('return_path')
    dkim_mail = request.json.get('dkim_mail')
    attachments = request.json.get('attachments')
    from_date = request.json.get('from_date')
    to_date = request.json.get('to_date')

    query = Mail.query
    if from_address:
        query = query.filter(Mail.fromMailAddress.ilike(f'%{from_address}%'))
    if to_address:
        query = query.filter(Mail.toMailAddress.ilike(f'%{to_address}%'))
    if cc_address:
        query = query.filter(Mail.ccMailAddress.ilike(f'%{cc_address}%'))
    if subject:
        query = query.filter(Mail.subject.ilike(f'%{subject}%'))
    if spf:
        query = query.filter(Mail.spf.ilike(f'%{spf}%'))
    if received_ip:
        query = query.filter(Mail.receivedIP.ilike(f'%{received_ip}%'))
    if uri_mail:
        query = query.filter(Mail.uriMail.ilike(f'%{uri_mail}%'))
    if return_path:
        query = query.filter(Mail.returnPath.ilike(f'%{return_path}%'))
    if dkim_mail:
        query = query.filter(Mail.dkimMail.ilike(f'%{dkim_mail}%'))
    if attachments:
        query = query.filter(Mail.attachments.ilike(f'%{attachments}%'))
    if from_date:
        query = query.filter(Mail.date >= from_date)
    if to_date:
        query = query.filter(Mail.date <= to_date)

    mails = query.paginate(page=page, per_page=10)

    mail_list = [mail.to_dict() for mail in mails.items]
    total_pages = mails.pages

    return jsonify(mails=mail_list, total_pages=total_pages)


#Rotating Main Page
@app.route('/')
def index():
    return render_template('index.html')

#IU
@app.route('/', methods=['POST'])
def upload_file():
    uploaded_file = request.files['file']
    filename = secure_filename(uploaded_file.filename)
    if uploaded_file.filename != '':
        file_ext = os.path.splitext(filename)[1]
        if file_ext not in app.config['UPLOAD_EXTENSIONS']:
            return 'Only .eml or .msg files allowed!'
        file_content = uploaded_file.stream.read()
        attachmentHash = calculate_hash(file_content)
        
        existing_mail = Mail.query.filter_by(attachmentHash=attachmentHash).first()
        if existing_mail:
            return 'File already exists in the database.'
        
        ep = eml_parser.EmlParser(include_attachment_data = True,
                                  include_raw_body = True,
                                      email_force_tld=False,
                                      domain_force_tld = False)
        parsed_eml = ep.decode_email_bytes(file_content)
        data = json.loads(json.dumps(parsed_eml, default=json_serial))
        data_json = json.dumps(parsed_eml, default=json_serial)
        #print(data_json)
        rawData = data_json
        #print(rawData)


        fromMailAddress = data["header"]["from"] 
        toMailAddress = data["header"]["to"] #list
        try:
            ccMailAddress = data["header"]["cc"] #list
        except:
            ccMailAddress = None
        date = data["header"]["date"]
        subject = data["header"]["subject"]
        try:
            receivedIP = data["header"]["received_ip"] #list
        except:
            receivedIP = None
        try:
            uriMail = data["body"][0]["uri"] #list
        except:
            uriMail = None
        ##
        try:
            spf = data["header"]["header"]["received-spf"] #list
        except:
            spf = None
        
        try:
            returnPath = data["header"]["header"]["return-path"] #list 
        except:
            returnPath = None
        try:    
            dkimMail=data["header"]["header"]["dkim-signature"] #list      
        except:
            dkimMail = None
        #
        try:
            attachmentName = [item["filename"] for item in data["attachment"]] #list 
            attachmentSize = [item["size"] for item in data["attachment"]] #list 
            attachmentMD5Hash = [item["hash"]["md5"] for item in data["attachment"]] #list 
            attachmentSHA256Hash = [item["hash"]["sha256"] for item in data["attachment"]] #list 
        except:
            attachmentName, attachmentSize, attachmentMD5Hash, attachmentSHA256Hash = None, None, None, None
        ##
        
        attachments = []

        try:
            for i in range(len(attachmentName)):
                attachment = {
                    'attachmentName': attachmentName[i],
                    'attachmentSize': attachmentSize[i],
                    'attachmentMD5Hash': attachmentMD5Hash[i],
                    'attachmentSHA256Hash': attachmentSHA256Hash[i]
                }
                attachments.append(attachment)
        except:
            print(":)")
        
        mailList = {
            "attachmentHash": attachmentHash,
            "fromMailAddress": str(fromMailAddress),
            "toMailAddress": str(toMailAddress),
            "ccMailAddress": str(ccMailAddress),
            "date": str(date),
            "subject": str(subject),
            "receivedIP": str(receivedIP),
            "uriMail": str(uriMail),
            "spf": str(spf),
            "returnPath": str(returnPath),
            "dkimMail": str(dkimMail),
            "attachments": str(attachments)
    }   
        
        

        print(mailList)

        mailListJson = json.dumps(mailList)
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
      

        cursor.execute(
            'INSERT INTO mail (fromMailAddress, toMailAddress, ccMailAddress, date, subject, receivedIP, uriMail, spf, returnPath, dkimMail, attachments, attachmentHash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (mailList['fromMailAddress'], mailList['toMailAddress'], mailList['ccMailAddress'], mailList['date'],
             mailList['subject'], mailList['receivedIP'], mailList['uriMail'], mailList['spf'], mailList['returnPath'],
             mailList['dkimMail'], mailList['attachments'], mailList['attachmentHash']))    

        conn.commit()
        conn.close()

    else:
        return 'error' 
    return 'Upload Successful'
   
    

if __name__=="__main__":
    app.run()