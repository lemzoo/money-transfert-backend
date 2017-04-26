#!/bin/sh
path=`dirname $0`

. $path/../../venv/bin/activate
. $path/../../sief-infra/back.settings
cd $path/..

core_analytics=`printenv SOLR_URL_ANALYTICS`
if [ 0 -eq $? ]
then 
	echo generate analytics on $core_analytics
	./manage.py analytics bootstrap -c $core_analytics
else
	echo No core specified
	./manage.py analytics bootstrap
fi