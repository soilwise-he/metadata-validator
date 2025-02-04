# import a range of records from a csw endpoint constraint by a filter

from dotenv import load_dotenv
import sys
from datetime import datetime
sys.path.append('utils')
from database import dbQuery

# Load environment variables from .env file
load_dotenv()

# which pycsw fields
flds="identifier,typename,schema,mdsource,insert_date,xml,anytext,metadata,metadata_type,language,type,title,title_alternate,abstract,edition,keywords,keywordstype,themes,parentidentifier,relation,time_begin,time_end,topicategory,resourcelanguage,creator,publisher,contributor,organization,securityconstraints,accessconstraints,otherconstraints,date,date_revision,date_creation,date_publication,date_modified,format,source,crs,geodescode,denominator,distancevalue,distanceuom,wkt_geometry,servicetype,servicetypeversion,operation,couplingtype,operateson,operatesonidentifier,operatesoname,degree,classification,conditionapplyingtoaccessanduse,lineage,responsiblepartyrole,specificationtitle,specificationdate,specificationdatetype,platform,instrument,sensortype,cloudcover,bands,links,contacts,anytext_tsvector,wkb_geometry"
# which fields are recommended # todo: could set a score per field
recflds={"identifier":10,
         "type":5,
         "title":25,
         "language":5,
         "abstract":20,
         "keywords":10,
         "time_begin":5,
         "time_end":5,
         "otherconstraints":5,
         "organization":10,
         "lineage":5 } 
# todo: some fields may need special processing, such as parse json and check inner value
# todo: some special rules based on type (document/dataset)

# get records which have not been validated for 10 days
recs = dbQuery("""select * from records2 limit 20""",(),True) # where identifier not in (select identifier from public.validated where date > NOW() - INTERVAL '10 DAYS')""",(),True)
loaded_files = []

if recs:
    total = len(recs)
    for rec in sorted(recs):
        md={}
        i=0
        for f0 in flds.split(','):
            md[f0] = rec[i]
            i+=1
        score=0
        # run check, which fields are required / optional
        for k,v in recflds.items():
            if md.get(k,'') not in [None,'']:
                score = score + v
        # insert score to db
        print(f"Result for {md.get('identifier','')} score {score}")
