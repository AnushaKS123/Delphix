#!/usr/bin/env python
# Corey Brune - Oct 2016
#This script starts or stops a VDB
#requirements
#pip install docopt delphixpy

#The below doc follows the POSIX compliant standards and allows us to use
#this doc to also define our arguments for the script.
"""List all VDBs or Start, stop, enable, disable a VDB
Usage:
  dx_operations_vdb.py (--vdb <name [--stop | --start | --enable | --disable] | --list)
                  [-d <identifier> | --engine <identifier> | --all]
                  [--debug] [--parallel <n>] [--poll <n>]
                  [--config <path_to_file>] [--logdir <path_to_file>]
  dx_operations_vdb.py -h | --help | -v | --version
List all VDBs, start, stop, enable, disable a VDB

Examples:
  dx_operations_vdb.py -d landsharkengine --vdb testvdb --stop

  dx_operations_vdb.py --vdb --start

Options:
  --vdb <name>              Name of the VDB to stop or start
  --start                   Stop the VDB
  --stop                    Stop the VDB
  --list                    List all databases from an engine
  --enable                  Enable the VDB
  --disable                 Disable the VDB
  -d <identifier>           Identifier of Delphix engine in dxtools.conf.
  --engine <type>           Alt Identifier of Delphix engine in dxtools.conf.
  --all                     Run against all engines.
  --debug                   Enable debug logging
  --parallel <n>            Limit number of jobs to maxjob
  --poll <n>                The number of seconds to wait between job polls
                            [default: 10]
  --config <path_to_file>   The path to the dxtools.conf file
                            [default: ./dxtools.conf]
  --logdir <path_to_file>    The path to the logfile you want to use.
                            [default: ./dx_operations_vdb.log]
  -h --help                 Show this screen.
  -v --version              Show version.
"""

VERSION = 'v.0.2.100'

from docopt import docopt
import logging
from os.path import basename
import sys
import time
import traceback
import json
from multiprocessing import Process
from time import sleep, time

from delphixpy.delphix_engine import DelphixEngine
from delphixpy.exceptions import JobError
from delphixpy.exceptions import RequestError
from delphixpy.exceptions import HttpError
from delphixpy import job_context
from delphixpy.web import database
from delphixpy.web import source
from delphixpy.web import host
from delphixpy.web import job
from delphixpy.web.capacity import consumer

from lib.DxTimeflow import DxTimeflow
from lib.DlpxException import DlpxException
from lib.GetSession import GetSession
from lib.GetReferences import find_obj_by_name
from lib.GetReferences import convert_timestamp
from lib.GetReferences import get_obj_reference
from lib.DxLogging import logging_est
from lib.DxLogging import print_info
from lib.DxLogging import print_debug


def vdb_operation(vdb_name, operation):
    """
    Function to start, stop, enable or disable a VDB
    """
    print_debug('Searching for %s reference.\n' % (vdb_name))

    vdb_obj = find_obj_by_name(dx_session_obj.server_session, source, vdb_name)

    try:
        if vdb_obj:
            if operation == 'start':
                source.start(server, vdb_obj.reference)
            elif operation == 'stop':
                source.stop(server, vdb_obj.reference)
            elif operation == 'enable':
                source.enable(server, vdb_obj.reference)
            elif operation == 'disable':
                source.disable(server, vdb_obj.reference)

    except (RequestError, HttpError, JobError, AttributeError), e:
        raise dlpxException('An error occurred while performing ' +
                            operation + ' on ' + vdb_name + '.:%s\n' % (e))

def list_databases():
    """
    Function to list all databases for a given engine
    """
    database_size = 0

    try:
        for db_stats in consumer.get_all(dx_session_obj.server_session):
            active_space = db_stats.breakdown.active_space/1024/1024/1024
            sync_space = db_stats.breakdown.sync_space/1024/1024/1024
            
            if db_stats.parent == None:
                db_stats.parent = 'dSource'

            print('name = %s\nprovision container= %s\ndatabase disk usage: '
                  '%.2f GB\nSize of Snapshots: %.2f GB\n' %
                  (str(db_stats.name), str(db_stats.parent),
                  db_stats.breakdown.active_space / 1024 / 1024 / 1024,
                  db_stats.breakdown.sync_space / 1024 / 1024 / 1024))

    except (RequestError, HttpError, JobError, AttributeError) as e:
        print 'An error occurred while listing databases on ' + \
              engine['ip_address'] + '.:%s\n' % (e)


def run_async(func):
    """
        http://code.activestate.com/recipes/576684-simple-threading-decorator/
        run_async(func)
            function decorator, intended to make "func" run in a separate
            thread (asynchronously).
            Returns the created Thread object
            E.g.:
            @run_async
            def task1():
                do_something
            @run_async
            def task2():
                do_something_too
            t1 = task1()
            t2 = task2()
            ...
            t1.join()
            t2.join()
    """
    from threading import Thread
    from functools import wraps

    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = Thread(target = func, args = args, kwargs = kwargs)
        func_hl.start()
        return func_hl

    return async_func


@run_async
def main_workflow(engine):
    """
    This function actually runs the jobs.
    Use the @run_async decorator to run this function asynchronously.
    This allows us to run against multiple Delphix Engine simultaneously

    engine: Dictionary of engines
    """
    jobs = {}

    try:
        #Setup the connection to the Delphix Engine
        dx_session_obj.serversess(engine['ip_address'], engine['username'],
                                  engine['password'])

        if arguments['--vdb']:
            #Get the database reference we are copying from the database name
            database_obj = find_obj_by_name(engine, server, database,
                                            arguments['--vdb'])

    except DlpxException as e:
        print_exception('\nERROR: Engine %s encountered an error while' 
                        '%s:\n%s\n' % (dx_session_obj.engine['hostname'],
                        arguments['--target'], e))
        sys.exit(1)

    thingstodo = ["thingtodo"]
    #reset the running job count before we begin
    i = 0
    with dx_session_obj.job_mode(single_thread):
        while (len(jobs) > 0 or len(thingstodo)> 0):
            if len(thingstodo)> 0:

                if arguments['--start']:
                    vdb_operation(database_name, 'start')

                elif arguments['--stop']:
                    vdb_operation(database_name, 'stop')

                elif arguments['--enable']:
                    vdb_operation(database_name, 'enable')

                elif arguments['--disable']:
                    vdb_operation(database_name, 'disable')

                elif arguments['--list']:
                    list_databases()

                thingstodo.pop()

            #get all the jobs, then inspect them
            i = 0
            for j in jobs.keys():
                job_obj = job.get(server, jobs[j])
                print_debug(job_obj)
                print_info(engine["hostname"] + ": VDB Operations: " +
                           job_obj.job_state)

                if job_obj.job_state in ["CANCELED", "COMPLETED", "FAILED"]:
                    #If the job is in a non-running state, remove it from the
                    # running jobs list.
                    del jobs[j]
                else:
                    #If the job is in a running state, increment the running
                    # job count.
                    i += 1

            print_info(engine["hostname"] + ": " + str(i) + " jobs running. ")
            #If we have running jobs, pause before repeating the checks.
            if len(jobs) > 0:
                sleep(float(arguments['--poll']))


def run_job():
    """
    This function runs the main_workflow aynchronously against all the servers
    specified
    """
    #Create an empty list to store threads we create.
    threads = []

    #If the --all argument was given, run against every engine in dxtools.conf
    if arguments['--all']:
        print_info("Executing against all Delphix Engines in the dxtools.conf")

        try:
            #For each server in the dxtools.conf...
            for delphix_engine in dx_session_obj.dlpx_engines:
                engine = dx_session_obj[delphix_engine]
                #Create a new thread and add it to the list.
                threads.append(main_workflow(engine))

        except DlpxException as e:
            print 'Error encountered in run_job():\n%s' % (e)
            sys.exit(1)

    elif arguments['--all'] is False:
        #Else if the --engine argument was given, test to see if the engine
        # exists in dxtools.conf
      if arguments['--engine']:
            try:
                engine = dx_session_obj.dlpx_engines[arguments['--engine']]
                print_info('Executing against Delphix Engine: %s\n' %
                           (arguments['--engine']))

            except (DlpxException, RequestError, KeyError) as e:
                raise DlpxException('\nERROR: Delphix Engine %s cannot be '                                         'found in %s. Please check your value '
                                    'and try again. Exiting.\n' % (
                                    arguments['--engine'], config_file_path))

      else:
          #Else search for a default engine in the dxtools.conf
          for delphix_engine in dx_session_obj.dlpx_engines:
              if dx_session_obj.dlpx_engines[delphix_engine]['default'] == \
                 'true':

                  engine = dx_session_obj.dlpx_engines[delphix_engine]
                  print_info('Executing against the default Delphix Engine '
                       'in the dxtools.conf: %s' % (
                       dx_session_obj.dlpx_engines[delphix_engine]['hostname']))

              break

          if engine == None:
              raise DlpxException("\nERROR: No default engine found. Exiting")

    #run the job against the engine
    threads.append(main_workflow(engine))

    #For each thread in the list...
    for each in threads:
        #join them back together so that we wait for all threads to complete
        # before moving on
        each.join()


def time_elapsed():
    """
    This function calculates the time elapsed since the beginning of the script.
    Call this anywhere you want to note the progress in terms of time
    """
    elapsed_minutes = round((time() - time_start)/60, +1)
    return elapsed_minutes


def main(argv):
    #We want to be able to call on these variables anywhere in the script.
    global single_thread
    global usebackup
    global time_start
    global config_file_path
    global database_name
    global dx_session_obj
    global debug

    if arguments['--debug']:
        debug = True

    try:
        dx_session_obj = GetSession()
        logging_est(arguments['--logdir'])
        print_debug(arguments)
        time_start = time()
        engine = None
        single_thread = False
        config_file_path = arguments['--config']
        #Parse the dxtools.conf and put it into a dictionary
        dx_session_obj.get_config(config_file_path)

        database_name = arguments['--vdb']

        #This is the function that will handle processing main_workflow for
        # all the servers.
        run_job()

        elapsed_minutes = time_elapsed()
        print_info("script took " + str(elapsed_minutes) +
                   " minutes to get this far.")

    #Here we handle what we do when the unexpected happens
    except SystemExit as e:
        """
        This is what we use to handle our sys.exit(#)
        """
        sys.exit(e)

    except HttpError as e:
        """
        We use this exception handler when our connection to Delphix fails
        """
        print_exception('Connection failed to the Delphix Engine'
                        'Please check the ERROR message below')
        sys.exit(1)

    except JobError as e:
        """
        We use this exception handler when a job fails in Delphix so that
        we have actionable data
        """
        elapsed_minutes = time_elapsed()
        print_exception('A job failed in the Delphix Engine')
        print_info('%s took %s minutes to get this far\n' %
                   (basename(__file__), str(elapsed_minutes)))
        sys.exit(3)

    except KeyboardInterrupt:
        """
        We use this exception handler to gracefully handle ctrl+c exits
        """
        print_debug("You sent a CTRL+C to interrupt the process")
        elapsed_minutes = time_elapsed()
        print_info('%s took %s minutes to get this far\n' %
                   (basename(__file__), str(elapsed_minutes)))

    except:
        """
        Everything else gets caught here
        """
        print_exception(sys.exc_info()[0])
        elapsed_minutes = time_elapsed()
        print_info('%s took %s minutes to get this far\n' %
                   (basename(__file__), str(elapsed_minutes)))
        sys.exit(1)

if __name__ == "__main__":
    #Grab our arguments from the doc at the top of the script
    arguments = docopt(__doc__, version=basename(__file__) + " " + VERSION)
    #Feed our arguments to the main function, and off we go!
    main(arguments)
