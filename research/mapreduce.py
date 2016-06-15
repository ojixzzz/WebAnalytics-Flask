from pymongo import MongoClient
from bson.code import Code
from datetime import datetime

mongoDB = MongoClient("localhost", 27018)
database = mongoDB.analytic
db_pageview = database.pageview

dtex1 = datetime.now()
print str(dtex1)

reducer = Code(
    """
    function(obj, result){
        result.count++;
    }
    """
)
stat_tahun_ini = db_pageview.group(
    key= Code('''function(doc) {
                    return { waktu: doc.created.getMonth() };
            }'''
    ), 
    condition={"id_domain": 1}, 
    initial={"count": 0}, 
    reduce=reducer
)
print "GRUOP"
print stat_tahun_ini

print str(datetime.now() - dtex1)
dtex1 = datetime.now()

mapper = Code("""
			function() {
		         emit ( this.created.getMonth(),  1);
		    }
		""")

reducer = Code("""
		function (key, values) {
         	return Array.sum(values);
     	}
	""")

result = db_pageview.map_reduce(mapper, reducer, "hasilnya")
print "MapReduce"
for doc in result.find():
	print doc

print str(datetime.now() - dtex1)
dtex1 = datetime.now()

    """
    stat_tahun_ini = db_pageview.group(
        key= Code('''function(doc) {
                        return { waktu: doc.created.getMonth() };
                }'''
        ), 
        condition={"time_bucket": dt_today.strftime('%Y-year'), "id_domain": id_domain}, 
        initial={"count": 0}, 
        reduce=reducer
    )
    """