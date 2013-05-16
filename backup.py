#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, sys, syslog, shutil
import time, string
import tarfile , ftplib, ConfigParser
from optparse import OptionParser, OptionGroup

#========================================================
#                 	Global Vars 
#========================================================
VERSION = "1.0"
VERSION_DATE = "May 15 2013 16:15:08"

TIME_BEGIN = time.clock()

#========================================================
#                    Functions 
#========================================================
def parseArgs():
	"""Parse any command line options."""

	parser = OptionParser()
	group = OptionGroup(parser, "Basics Options")
	group.add_option("-c", "--conffile", dest="conffile", help="Config file")
	group.add_option("-p", "--period", dest="period", help="Period : hourly / daily / weekly / monthly / yearly", default='daily')
	group.add_option("-t", "--tmpdir", dest="tmp", help="Temporary working directory (by default /tmp)", default="/tmp")
	parser.add_option_group(group)
	group = OptionGroup(parser, "Program Options")
	group.add_option("--template", dest="template", help="Create config file example", default="False")
	group.add_option("-d", "--debug", dest="debug", action="store_true", help="Print debug information", default="False")
	group.add_option("-v", "--version", dest="version", action="store_true", help="Print version information and exit", default="False")
	parser.add_option_group(group)
	(options, args) = parser.parse_args()


	# Print version information
	if options.version == True:
		print "Backup v%s (modified %s)" %(VERSION, VERSION_DATE)
		print "Created by Steven Ducastelle"
		sys.exit(0)

	# Create template config file
	if options.template != "False":
		createTemplate(options)

	# Print error and help if no argument is passed
	if ((options.conffile is None) and (options.template == "False")):
		sys.stderr.write("Missing argument(s).\n")
		sys.stderr.write(parser.parse_args(["--help"]))

	return (options, args)


def createTemplate(options):
	"""Create template config file in specific dir"""

	tmpFile = options.template
	content="""[backup]
; Name of backup
name=backup1
syslog=True

; List files to backup separate with coma
files: /etc/fstab,/root/.bashrc

; List directories to backup separate with coma
dirs= /var/www,/var/lib

; backup Mysql
mysqldb= db1,db2
userdb=adminsql
passdb=password!


# Dir / Mount / NFS
[export-fs]
enable=False
dest=/tmp
; Separate multi destination with coma

# By SCP
; Use authentication with certificate
[export-scp]
enable=False
host=
user=
dest=

# By RSYNC with ssh
[export-rsync]
enable=False
host=
user=
pass=
dest=

# By FTP
[export-ftp]
enable=False
host=
user=
pass=
dest=
"""
	tmpFile = open(tmpFile, 'w')
	tmpFile.write(content) 
	tmpFile.close()
	sys.exit(0)
	return True


def splitComa(data):
	"""Split string"""
	return string.split(str(data), ',')


def logger(data):
	"""Write in syslog and debug if asked by user"""
	if str(config.get('backup', 'syslog')).lower() == 'true':
		syslog.syslog(syslog.LOG_INFO, 'backup.py ' + data)

	if options.debug is True:
		print '>>> DEBUG (',time.clock(),') :',data

	return True


def formatPath(data):
	"""Format path in same syntax"""

	# Supress the / at the end
	if data[-1] == '/':
		data = data[:-1]

	return data


def humanSizeof(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')


#========================================================
#                       Main 
#========================================================
# Get the command line options and arguments:
(options, args) = parseArgs()

# Open config file
config = ConfigParser.RawConfigParser()
# read config file
config.read(options.conffile)

logger("Backup start (" + str(config.get('backup', 'name')) + ') - Type : ' + str(options.period));


# Creating temporary dir
tmpPath = formatPath(options.tmp) + '/backup-' + time.strftime("%Y%m%d_%Hh%M") + '_' + options.period
if not os.path.exists(tmpPath): 
	try:
		os.makedirs(tmpPath)
	except OSError, e:
		logger('Error when creating temporary directory : ' + str(e))
		sys.exit(1)



# Creating archive
tarName = 'backup-' + time.strftime("%Y%m%d_%Hh%M") + '_' + options.period + '.tar.gz'
logger('Creating archive (' + tarName + ') ...')
tar = tarfile.open(tmpPath + '/' + tarName, "w:gz")

# Add each file
for f in splitComa(config.get('backup', 'files')):
	tar.add(f.strip())

# Add each dir
for d in splitComa(config.get('backup', 'dirs')):
	tar.add(d.strip())


# Dump Mysql
if config.get('backup', 'mysqldb') != '':
	logger('MySQL dump bases...')
	bases = splitComa(config.get('backup', 'mysqldb'))
	for db in bases:
		db = db.strip()
		fdb = "dump-Mysql_" + db + "_" + time.strftime("%Y%m%d_%Hh%M") + ".sql"
		logger('Dump base ' + db)
		# Dump mysql
		os.system("mysqldump --add-drop-table -c -u " + config.get('backup', 'userdb') + " -p" + config.get('backup', 'passdb') + " " + db + " > " + tmpPath + "/" + fdb)
		# Add file in archive backup
		tar.add(tmpPath + "/" + fdb, arcname=fdb)

	logger('MySQL dump completed')

# Close archive 
tar.close()
arcSize = humanSizeof(os.path.getsize(tmpPath + '/' + tarName))
logger('Archive completed')



# Exports
## Export FS
if str(config.get('export-fs', 'enable')).lower() == 'true':
	# for each destination
	for fs in splitComa(config.get('export-fs', 'dest')):
		fs = formatPath(fs)
		logger('Export to directory (' + fs + '/' + config.get('backup', 'name') + '/' + str(options.period) + ') ...')
		
		# Create directory if not exist
		try:
			if not os.path.exists(fs + '/' + config.get('backup', 'name') + '/' + str(options.period)): 
				os.makedirs(fs + '/' + config.get('backup', 'name') + '/' + str(options.period))

			# Copy file in directory
			try:
				shutil.copyfile(tmpPath + '/' + tarName, fs + '/' + config.get('backup', 'name') + '/' + str(options.period) + '/' + tarName )
			except IOError, e:
				logger('Error during file export : ' + str(e))

		except OSError, e:
			logger('Error when creating temporary directory : ' + str(e))

	logger('Directory export completed')


## Export SCP
if str(config.get('export-scp', 'enable')).lower() == 'true':
	logger('Export to SCP (' + str(config.get('export-scp', 'host')) + ')...')
	os.system("scp " + tmpPath + '/' + tarName + " " + str(config.get('export-scp', 'user')).strip() + "@" + str(config.get('export-scp', 'host')).strip() + ":" + formatPath(config.get('export-scp', 'dest')) + " > /dev/null")
	logger('SCP export completed')


## Export RSYNC
if str(config.get('export-rsync', 'enable')).lower() == 'true':
	logger('Export to RSYNC (' + str(config.get('export-rsync', 'host')) + ')...')
	os.system("rsync -e ssh -az  " + tmpPath + '/' + tarName + " " + str(config.get('export-rsync', 'user')).strip() + "@" + str(config.get('export-rsync', 'host')).strip() + ":" + formatPath(config.get('export-rsync', 'dest')) + " > /dev/null")
	logger('RSYNC export completed')


## Export FTP
if str(config.get('export-ftp', 'enable')).lower() == 'true':
	logger('Export to FTP (' + str(config.get('export-ftp', 'host')) + ')...')
	try:
		ftp = ftplib.FTP(config.get('export-ftp','host'), config.get('export-ftp','user'), config.get('export-ftp','pass'))
		ftp.cwd(str(config.get('export-ftp', 'dest')).strip())
		ftp.storbinary(('STOR ' + config.get('export-ftp', 'dest') + '/' + tarName).encode('utf-8'), open(tmpPath + '/' + tarName, 'rb'))
	except Exception, e:
		logger('Error to FTP export : ' + str(e))

	logger('FTP export completed')



# Deleting temporary files
try:
	shutil.rmtree(tmpPath)
except OSError, e:
	logger('Error when deleting temporary directory : ' + str(e))


timeExecution = time.clock() - TIME_BEGIN
logger('Backup completed, size:' + str(arcSize) + ' (time execution:' + str(timeExecution) + 's)')

