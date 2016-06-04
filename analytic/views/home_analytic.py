from base64 import b64decode
import json
import os
import calendar
from urlparse import parse_qsl, urlparse
from flask import Flask, Response, abort, request, render_template
from pymongo import MongoClient
from bson.code import Code
from datetime import datetime, timedelta, date
from analytic import app
from analytic.config import DOMAIN, MONGO_HOST, MONGO_PORT

BEACON = b64decode('R0lGODlhAQABAIAAANvf7wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==')
JAVASCRIPT = """(function(){
    var d=document,i=new Image,e=encodeURIComponent;
    i.src='%s/analytic.gif?url='+e(d.location.href)+'&ref='+e(d.referrer)+'&t='+e(d.title);
    })()""".replace('\n', '')

app.config.from_object(__name__)
mongoDB = MongoClient(MONGO_HOST, MONGO_PORT)
database = mongoDB.analytic

def get_month_range(start_date=None):
    if start_date is None:
        start_date = date.today().replace(day=1)
    _, days_in_month = calendar.monthrange(start_date.year, start_date.month)
    end_date = start_date + timedelta(days=days_in_month)
    return (start_date, end_date)

def recordPageView():
    dt = datetime.today()
    parsed = urlparse(request.args['url'])
    params = dict(parse_qsl(parsed.query))

    db_pageview = database.pageview
    dataout = {
        'id_domain': 1,
        'domain' : parsed.netloc,
        'url' : parsed.path,
        'title' : request.args.get('t') or '',
        'ip' : request.headers.get('X-Forwarded-For', request.remote_addr),
        'referrer' : request.args.get('ref') or '',
        'headers' : dict(request.headers),
        'params' : params,
        'created': dt,
        'time_bucket': [
            "%s-minute" % dt.strftime("%Y-%m-%d %H-%M") ,
            "%s-hour" % dt.strftime("%Y-%m-%d %H"),
            "%s-day" % dt.strftime("%Y-%m-%d"),
            "%s-month" % dt.strftime("%Y-%m"),
            "%s-year" % dt.strftime("%Y")
        ]
    }
    return db_pageview.insert_one(dataout).inserted_id

@app.route('/analytic.gif')
def analyze():
    if not request.args.get('url'):
        abort(404)

    recordPageView()
    response = Response(app.config['BEACON'], mimetype='image/gif')
    response.headers['Cache-Control'] = 'private, no-cache'
    return response

@app.route('/analytic.js')
def script():
    return Response(app.config['JAVASCRIPT'] % DOMAIN, mimetype='text/javascript')

@app.route('/munyuk.html')
def munyuk():
    return Response('''OKEE<script src="http://localhost:5000/analytic.js"></script>''', mimetype='text/html') 

@app.errorhandler(404)
def not_found(e):
    return Response('Not found.')

def is_stat_exist(stat, x):
    for row in stat:
        if int(row['waktu'])==x:
            row['count']=int(row['count'])
            row['waktu']=int(row['waktu'])
            return row
    return False

@app.route('/')
def report():
    id_domain = 1
    db_pageview = database.pageview

    dt_today = datetime.today()
    dt_menit_sebelum = dt_today-timedelta(minutes=1)
    dt_hari_sebelum = dt_today-timedelta(days=1)
    dt_bulan_sebelum = dt_today.replace(day=1) - timedelta(days=1)

    try:
        dt_tahun_sebelum = dt_today.replace(year=dt_today.year-1)
    except ValueError:
        dt_tahun_sebelum = dt_today.replace(year=dt_today.year-1, day=dt_today.day-1)

    reducer = Code(
        """
        function(obj, result){
            result.count++;
        }
        """
    )

    stat_menit_ini = db_pageview.group(
        key= Code('''function(doc) {
                        return { waktu: doc.created.getSeconds() };
                }'''
        ), 
        condition={"time_bucket": dt_today.strftime('%Y-%m-%d %H-%M-minute'), "id_domain": id_domain}, 
        initial={"count": 0}, 
        reduce=reducer
    )
    statistik = []
    for x in range(1, 60):
        dtstat = is_stat_exist(stat_menit_ini, x)
        if not dtstat:
            dtstat = {
                'waktu': x, 
                'count': 0
            }
        statistik.append(dtstat)
    stat_menit_ini = statistik
    count_menit_ini = db_pageview.count({"time_bucket": dt_today.strftime('%Y-%m-%d %H-%M-minute'), "id_domain": id_domain})
    count_menit_sebelum = db_pageview.count({"time_bucket": dt_menit_sebelum.strftime('%Y-%m-%d %H-%M-minute'), "id_domain": id_domain})

    stat_hari_ini = db_pageview.group(
        key= Code('''function(doc) {
                        return { waktu: doc.created.getHours() };
                }'''
        ), 
        condition={"time_bucket": dt_today.strftime('%Y-%m-%d-day'), "id_domain": id_domain}, 
        initial={"count": 0}, 
        reduce=reducer
    )
    statistik = []
    for x in range(0, 23):
        dtstat = is_stat_exist(stat_hari_ini, x)
        if not dtstat:
            dtstat = {
                'waktu': x, 
                'count': 0
            }
        statistik.append(dtstat)
    stat_hari_ini = statistik
    count_hari_ini = db_pageview.count({"time_bucket": dt_today.strftime('%Y-%m-%d-day'), "id_domain": id_domain})
    count_hari_sebelum = db_pageview.count({"time_bucket": dt_hari_sebelum.strftime('%Y-%m-%d-day'), "id_domain": id_domain})

    stat_bulan_ini = db_pageview.group(
        key= Code('''function(doc) {
                        return { waktu: doc.created.getDate() };
                }'''
        ), 
        condition={"time_bucket": dt_today.strftime('%Y-%m-month'), "id_domain": id_domain}, 
        initial={"count": 0}, 
        reduce=reducer
    )
    statistik = []
    for x in range(1, 31):
        dtstat = is_stat_exist(stat_bulan_ini, x)
        if not dtstat:
            dtstat = {
                'waktu': x, 
                'count': 0
            }
        statistik.append(dtstat)
    stat_bulan_ini = statistik
    count_bulan_ini = db_pageview.count({"time_bucket": dt_today.strftime('%Y-%m-month'), "id_domain": id_domain})
    count_bulan_sebelum = db_pageview.count({"time_bucket": dt_bulan_sebelum.strftime('%Y-%m-month'), "id_domain": id_domain})

    stat_tahun_ini = db_pageview.group(
        key= Code('''function(doc) {
                        return { waktu: doc.created.getMonth() };
                }'''
        ), 
        condition={"time_bucket": dt_today.strftime('%Y-year'), "id_domain": id_domain}, 
        initial={"count": 0}, 
        reduce=reducer
    )
    statistik = []
    for x in range(1, 12):
        dtstat = is_stat_exist(stat_tahun_ini, x)
        if not dtstat:
            dtstat = {
                'waktu': x, 
                'count': 0
            }
        statistik.append(dtstat)
    stat_tahun_ini = statistik
    count_tahun_ini = db_pageview.count({"time_bucket": dt_today.strftime('%Y-year'), "id_domain": id_domain})
    count_tahun_sebelum = db_pageview.count({"time_bucket": dt_bulan_sebelum.strftime('%Y-year'), "id_domain": id_domain})

    data = {
        "count_menit_ini": count_menit_ini,
        "count_menit_sebelum": count_menit_sebelum,
        "count_hari_ini": count_hari_ini,
        "count_hari_sebelum": count_hari_sebelum,
        "count_bulan_ini": count_bulan_ini,
        "count_bulan_sebelum": count_bulan_sebelum,
        "count_tahun_ini": count_tahun_ini,
        "count_tahun_sebelum": count_tahun_sebelum,
        "stat_menit_ini": stat_menit_ini,
        "stat_hari_ini": stat_hari_ini,
        "stat_bulan_ini": stat_bulan_ini,
        "stat_tahun_ini": stat_tahun_ini,
    }
    return render_template('home_analytic.html', data=data)
