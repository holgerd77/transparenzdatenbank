
import requests
from pyquery import PyQuery
import re
from pygeocoder import Geocoder,GeocoderError

class Listing(object):
  
  def __init__(self,year=2011,url="http://www.transparenzdatenbank.at/trans/"):
    self.url=url
    self.year=year
    self.hiddenfields=None

  def get_hiddenfields(self):
    params={"bundesland":0,"betrag":"0,0","betrag_jahr":self.year,"numberOfLinesPerPage":"100","name":""}
    r=requests.post("%ssee.through"%self.url,data=params)
    if r.status_code==200:
      pq=PyQuery(r.text)
      self.hiddenfields=pq("form:eq(1) input").val()
      self.max=self.hiddenfields.split("|")[1]
      return (self.hiddenfields,self.max)
    else:
      return None
  
  def get_listing(self,number):
    if not self.hiddenfields:
      self.get_hiddenfields()
    params={"hiddenfields":self.hiddenfields, "move":u'\xA0%d\xA0'%number}
    r=requests.post("%sshow.detail"%self.url,data=params)
    pq=PyQuery(r.text)
    def extract_values(form):
      return dict([(x.name,x.value) for x in pq("input",form)])
    
    pages=[Page(self.url,extract_values(form)) for form in 
      pq("table.border > tr > td.center > form")]
    return pages

  def get_all_listings(self):
    return reduce(lambda x,y: x+y, 
      map(lambda x: self.get_listing(x),range(1,self.max+1)))

  def save_csv(self,filename):
    pages=self.get_all_listings()
    f=open(filename,"w")
    f.write("%s/n"%",".join(pages[0].order))
    for page in pages:
      f.write(page.csv())
    f.close()  
    
class Page(object):
  order=["unique","ukey","name","ort","lat","lon","program","amount","year"]
  
  def __init__(self,url="http://www.transparenzdatenbank.at/trans/",params=None):
    self.url="%sshow.detail"%url
    self.params=params
    
  def get_html(self):
    r=requests.post(self.url,data=self.params)
    if r.status_code==200:
      self.html=r.text
      return self.html
    else:
      return None
  def get_items(self):
    pq=PyQuery(self.get_html())
    rows=pq("table.border tr")
    rows.pop()
    rows.pop(0) # remove first and last - heading and summary
    def extract_items(row):
      program=pq("td:eq(0)",row).html()
      amount=pq("td:eq(1)",row).html()
      amount=float(re.sub("[^0-9,]","",amount).replace(",","."))
      return {"amount":amount,"program":program}

    items=[extract_items(row) for row in rows]
    return items
 
  def get_geocode(self):
    location=self.params["location"].encode("utf-8")
    try:
      geo=Geocoder.geocode(location)
    except GeocoderError:
      try:
        geo=Geocoder.geocode("%s, Austria"%location.split(",")[1])
      except GeocoderError:
        return None
    
    return geo.coordinates
    

  def get_records(self):
    (name,ort)=self.params["location"].encode("utf-8").split(",")
    name.strip()
    ort.lstrip()
    geo=self.get_geocode()
    if geo:
      (lat,lon)=self.get_geocode()
    else:
      (lat,lon)=(None,None)
    year=int(re.sub("[^0-9]","",self.params["year"]))
    unique=self.params["unique"]

    def construct_record(item):
      return dict(item.items()+[("name",name.decode("utf-8")),("ort",ort.decode("utf-8")),("lat",lat),
      ("lon",lon),("year",year),("unique",unique),("ukey",u"%s-%s"%(unique,item["program"]))])

    return [construct_record(i) for i in self.get_items()] 
  
  def csv(self):
    def line(r):
      return u",".join([u"%s"%r[i] for i in self.order])

    return u"%s\n"%"\n".join([line(r) for r in self.get_records()])  
