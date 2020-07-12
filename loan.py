#!/usr/bin/env python
# -*- coding:utf-8 -*-

import csv
import json
import os
import random
import re
import requests
import sqlite3
import sys
import time
import traceback

from bs4 import BeautifulSoup

hds = [{'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'},
       {'User-Agent': 'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'},
       {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'},
       {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0'},
       {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/44.0.2403.89 Chrome/44.0.2403.89 Safari/537.36'},
       {'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'},
       {'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'},
       {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0'},
       {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'},
       {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'},
       {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'},
       {'User-Agent': 'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; en) Presto/2.8.131 Version/11.11'},
       {'User-Agent': 'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11'}]

def randomSleep(minS, maxS):
    time.sleep(random.uniform(minS, maxS))

def reprDict(data):
    return json.dumps(data, ensure_ascii=False, indent=4, sort_keys=True)

def getMatchString(content, pattern):

    matches = re.findall(pattern, content)

    if matches is None or 0 == len(matches):
        return None

    return matches[0]

def check_block(soup):
    if soup.title.string == "414 Request-URI Too Large":
        logging.error(
            "Lianjia block your ip, please verify captcha manually at lianjia.com")
        return True
    return False

def getLoan(htmlContent):

    soup = BeautifulSoup(htmlContent, 'lxml')

    check_block(soup)

    names = ['introContent', 'transaction', 'content']

    data = soup

    for name in names:
        data = data.find('div', {'class': name})
        if data is None:
            return None

    spans = data.findAll('span', {'class': 'label'})

    for span in spans:

        key = span.get_text().strip()

        if '抵押信息' == key:
            data = span.parent
            break
    else:
        return None

    spans = data.findAll('span')

    for span in spans:

        key = span.get_text().strip()

        if '抵押信息' == key:
            continue

        loan = span.get_text().strip()
        return loan

    return None

def getLoanFromFile(htmlfile):

    with open(htmlfile) as fp:
        content = fp.read()

    return getLoan(content)

def save(url):

    pos = url.rfind('/')

    if pos < 0:
        print('Invalid URL:', url)
        return None

    pathname = 'html/{}'.format(url[pos+1:])

    if os.path.exists(pathname):
        return pathname

    try:
        print('Getting:', pathname)

        r = requests.get(
            url, headers=hds[random.randint(0, len(hds) - 1)])

        with open(pathname, 'wb') as fp:
            fp.write(r.content)
            print('Saved:', pathname, 'with', len(r.content))

        randomSleep(0.5, 1.5)

    except Exception as e:
        print('Failed to get', url, ':', e)

    return pathname

def retrieveLoans(datas):

    houses = list()
    num = len(datas)

    for index in range(num):

        data = datas[index]

        house = dict()

        fields = ['houseId', 'roomNum', 'districtName', 'communityName', 'price', 'buildingArea', 'buildYear', 'viewUrl']

        for pos in range(len(fields)):

            field = fields[pos]
            house[field] = data[pos]

        url = house['viewUrl']

        pathname = save(url)

        if pathname is None:
            continue

        loan = getLoanFromFile(pathname)
        if loan is None:
            continue

        if '无抵押' == loan:
            continue

        pattern = r'[^0-9]*([0-9]+?)[^0-9]+'

        money = getMatchString('{}END'.format(loan), pattern)

        if money is None:
            money = 0
        else:
            money = int(float(money))

        house['loan'] = money
        house['loanDescription'] = loan

        print('{:5}/{} {:>4} {} {:24}'.format(index, num, money, house['districtName'], house['communityName']), loan, house['houseId'])

        houses.append(house)

    houses = sorted(houses, key=lambda data: data['loan'], reverse=True)

    with open('data/loans.json', 'w') as fp:
        fp.write(reprDict(houses))

    with open('data/loans.csv', 'w', newline='') as csvfile:

        writer = None

        for house in houses:

            if writer is None:
                writer = csv.DictWriter(csvfile, fieldnames=house.keys())
                writer.writeheader()

            writer.writerow(house)

def testGetLoanFromFile():

    if len(sys.argv) < 2:
        print('Usage:\n\t', sys.argv[0], 'html-file\n')
        exit()

    htmlfile = os.path.realpath(sys.argv[1])

    loan = getLoanFromFile(htmlfile)
    print(loan)

def testRetrieveLoans():

    sql = '''
        SELECT houseId, roomNum, districtName, communityName, price, buildingArea, buildYear, viewUrl
        FROM 北京
        WHERE price >= 500 and price <= 900
        and buildingArea >= 90 and buildingArea < 140
        and unitPrice >= 50000
        and buildYear >= "2000年建" and buildYear <= "2015年建" 
        and districtName in ("朝阳", "丰台")
        and (roomNum like "%2%" or roomNum like "%3%")
        ORDER by buildYear desc, buildingArea
    '''

    with sqlite3.connect('data/DetailInfo.db') as conn:

        c = conn.cursor()
        c.execute(sql)
        datas = c.fetchall()

    retrieveLoans(datas)

if __name__ == '__main__':

    testGetLoanFromFile()
    #testRetrieveLoans()

