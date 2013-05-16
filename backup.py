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
DATE = time.strftime("%Y%m%d_%Hh%M")

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


# Vars
tmpPath = formatPath(options.tmp) + '/backup-' + DATE + '_' + options.period
tarName = 'backup-' + DATE + '_' + options.period + '.tar.gz'
tarPath = tmpPath + '/' + tarName

config = ConfigParser.RawConfigParser()					# Open config file
config.read(options.conffile)							# read config file

logger("Backup start (" + str(config.get('backup', 'name')) + ') - Type : ' + str(options.period));


# Creating temporary dir
if not os.path.exists(tmpPath): 
	try:
		os.makedirs(tmpPath)
	except OSError, e:
		logger('Error when creating temporary directory : ' + str(e))
		sys.exit(1)



# Creating archive
tar = tarfile.open(tarPath, "w:gz")
logger('Creating archive (' + tarName + ') ...')

################################
# Backup files and directories #
################################
for f in splitComa(config.get('backup', 'files')):		# Add each file
	tar.add(f.strip())

for d in splitComa(config.get('backup', 'dirs')):		# Add each dirs
	tar.add(d.strip())

##############
# Dump Mysql #
##############
if config.get('backup', 'mysqldb') != '':
	logger('MySQL dump bases...')
	bases = splitComa(config.get('backup', 'mysqldb'))	# Fetches the list of databases
	for db in bases:
		db = db.strip()									# Removes spaces at the beginning and end of the character string
		fdb = "dump-Mysql_" + db + "_" + DATE + ".sql"	# Name of dump sql file
		logger('Dump base ' + db)
		os.system("mysqldump --add-drop-table -c -u " + config.get('backup', 'userdb') + " -p" + config.get('backup', 'passdb') + " " + db + " > " + tmpPath + "/" + fdb)		# Dump 
		tar.add(tmpPath + "/" + fdb, arcname=fdb)		# Add file in archive backup

	logger('MySQL dump completed')


tar.close()												# Close archive
arcSize = humanSizeof(os.path.getsize(tarPath))			# Size of archive
logger('Archive completed')


###########
# Exports #
###########

# Export in filesytem or mount point
if str(config.get('export-fs', 'enable')).lower() == 'true':
	for fs in splitComa(config.get('export-fs', 'dest')):	# Fetches the list of destination
		fs = formatPath(fs)									# Clean path
		logger('Export to directory (' + fs + '/' + config.get('backup', 'name') + '/' + str(options.period) + ') ...')
		
		try:
			if not os.path.exists(fs + '/' + config.get('backup', 'name') + '/' + str(options.period)): 	# Create directory if not exist
				os.makedirs(fs + '/' + config.get('backup', 'name') + '/' + str(options.period))

			try:
				shutil.copyfile(tarPath, fs + '/' + config.get('backup', 'name') + '/' + str(options.period) + '/' + tarName )		# Copy file in directory
			except IOError, e:
				logger('Error during file export : ' + str(e))

		except OSError, e:
			logger('Error when creating temporary directory : ' + str(e))

	logger('Directory export completed')


## Export SCP
if str(config.get('export-scp', 'enable')).lower() == 'true':
	logger('Export to SCP (' + str(config.get('export-scp', 'host')) + ')...')
	os.system("scp " + tarPath + " " + str(config.get('export-scp', 'user')).strip() + "@" + str(config.get('export-scp', 'host')).strip() + ":" + formatPath(config.get('export-scp', 'dest')) + " > /dev/null")		# Copy tar.gz with scp
	logger('SCP export completed')


## Export RSYNC
if str(config.get('export-rsync', 'enable')).lower() == 'true':
	logger('Export to RSYNC (' + str(config.get('export-rsync', 'host')) + ')...')
	os.system("rsync -e ssh -az  " + tarPath + " " + str(config.get('export-rsync', 'user')).strip() + "@" + str(config.get('export-rsync', 'host')).strip() + ":" + formatPath(config.get('export-rsync', 'dest')) + " > /dev/null")		# Copy tar.gz with rsync
	logger('RSYNC export completed')


## Export FTP
if str(config.get('export-ftp', 'enable')).lower() == 'true':
	logger('Export to FTP (' + str(config.get('export-ftp', 'host')) + ')...')
	try:
		ftp = ftplib.FTP(config.get('export-ftp','host'), config.get('export-ftp','user'), config.get('export-ftp','pass'))		# Ftp connection
		ftp.cwd(str(config.get('export-ftp', 'dest')).strip())																	# Go to the destination directory
		ftp.storbinary(('STOR ' + config.get('export-ftp', 'dest') + '/' + tarName).encode('utf-8'), open(tarPath, 'rb'))		# Upload tar.gz
	except Exception, e:
		logger('Error to FTP export : ' + str(e))

	logger('FTP export completed')



# Deleting temporary files
try:
	shutil.rmtree(tmpPath)
except OSError, e:
	logger('Error when deleting temporary directory : ' + str(e))


timeExecution = time.clock() - TIME_BEGIN					# Calculate time execution	
logger('Backup completed, size:' + str(arcSize) + ' (time execution:' + str(timeExecution) + 's)')

