import subprocess
import sys
import getopt
import datetime, time


ARGS={}
APTLY_EXEC='/usr/bin/aptly'
TIMESTAMP = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H-%M-%S')

def run_command(command):
    print "Running: {}".format(command)
    p=subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out,err=p.communicate()
    if p.returncode != 0 :
        raise BaseException("{}".format(err or out))
    return out.split()

def create_snapshots_map():
    snapshots_map={}
    snapshots_all=run_command(APTLY_EXEC+" snapshot list -raw")
    mirrors=run_command(APTLY_EXEC+" mirror list -raw")
    timestamps={ snapshot.split('_')[-1] for snapshot in snapshots_all}
    distributions= { snapshot.split('_')[1] for snapshot in snapshots_all}
    for timestamp in timestamps:
        TEMP_MAP={}
        snapshots=[snap for snap in snapshots_all if timestamp == snap.split('_')[-1]]
        for distribution in distributions:
            common_snaps=[snapshot for snapshot in snapshots if snapshot.split('_')[1] == distribution]
            if len(common_snaps) > 0:
                TEMP_MAP.update({distribution:common_snaps})
        snapshots_map.update({timestamp:TEMP_MAP})
    return snapshots_map


def aptly_create_mirrors():
    existing_mirrors=run_command(APTLY_EXEC+" mirror list -raw")
    for component in ARGS['COMPONENTS']:
        if ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component not in existing_mirrors:
            run_command(APTLY_EXEC+" mirror create -architectures="+ARGS['ARCHS']+" "+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component+' '+ARGS['URL']+' '+ARGS['DIST']+' '+component)
        else:
            print "Not creating mirror: {} as mirror already present".format(ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component)
        

def aptly_update_mirrors():
    for component in ARGS['COMPONENTS']:
        run_command(APTLY_EXEC+" mirror update "+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component)
    

def aptly_create_snapshots():
    for component in ARGS['COMPONENTS']:
        run_command(APTLY_EXEC+" snapshot create "+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component+'_'+TIMESTAMP+' from mirror '+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component)


def aptly_publish(timestamp):
    snapshots_map=create_snapshots_map()
    print "inside publish"
    print snapshots_map
    for item in snapshots_map[timestamp].items():
        if item[0] == ARGS['DIST']:
            temp_s1=""
            temp_s2=","*(len(item[1])-1)
            for snapshot in item[1]:
              temp_s1+=snapshot+" "
            run_command(APTLY_EXEC+" publish snapshot -component="+temp_s2+" -distribution="+ARGS['DIST']+" "+temp_s1+" "+ARGS['PUBLISH']+'/'+timestamp)

def aptly_housekeep(keep):
    print "housekeeping"
    published_snapshots=run_command(APTLY_EXEC+ " publish list -raw")
    print "published: {}".format(published_snapshots)
    indices=[index for index in range(0,len(published_snapshots),2) if published_snapshots[index+1] == ARGS['DIST']]
    print "indices: {}".format(indices)
    sorted_timestamps=sorted([published_snapshots[index] for index in indices])[:len(indices)-keep]
    for timestamp in sorted_timestamps:
        run_command(APTLY_EXEC+ " publish drop "+ARGS['DIST']+" "+timestamp)
          
def display_usage():
    print """   aptly.py -d[--distribution] <distribution> -u[--url] <url> -p[--publish] <publish_path>"

                arguments:
                      -h[--help]         : prints this message
                      -d[distribution]   : distribution eg. vivid or vivid-updates
                      -u[url]            : src url eg. http://ie.archive.ubuntu.com/ubuntu
                      -p[publish]        : path to publish the repo
                      -a[--architectures]: comma separated list of architectures to download packages for. eg. -a amd64,i386; defaults to amd64
                      -c[--components]   : comma separated list of components to download. eg. -c main,universe
                      -s[--suffix]       : snapshot suffix; defaults to TIMESTAMP of format '%Y-%m-%d-%H-%M-%S' at the time of running the script
                      -k[--keep]         : keep this many snapshots (per distribution) and delete the rest while housekeeping; default 30

          """                     

def main(argv):

    global ARGS
    global TIMESTAMP


    try:
        opts, args = getopt.getopt(argv,"ha:c:d:u:p:s:k:",["help","filters=","architectures=","components=","distributions=","url=", "publish=","suffix=","keep="])
    except getopt.GetoptError:
        display_usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            display_usage()
            sys.exit()
        elif opt in ("-d", "--distribution"):
            ARGS.update({"DIST":arg})
        elif opt in ("-u", "--url"):
            ARGS.update({"URL":arg})
        elif opt in ("-p", "--publish"):
            ARGS.update({"PUBLISH":arg})
        elif opt in ("-a", "--architectures"):
            ARGS.update({"ARCHS":arg})
        elif opt in ("-c", "--components"):
            ARGS.update({"COMPONENTS":arg.split(',')})
        elif opt in ("-s", "--suffix"):
            ARGS.update({"SUFFIX":arg})
        elif opt in ("-k", "--keep"):
            ARGS.update({"KEEP":arg})

    if 'ARCHS' not in ARGS:
        ARGS.update({"ARCHS":"amd64"})
    if 'KEEP' not in ARGS:
        ARGS.update({"KEEP":30})
    if 'SUFFIX' in ARGS:
        TIMESTAMP=ARGS['SUFFIX']
        

    try:
        print ARGS
        aptly_create_mirrors()
        aptly_update_mirrors()
        aptly_create_snapshots()
        aptly_publish(TIMESTAMP)
        aptly_housekeep(int(ARGS['KEEP']))
    except BaseException:
        raise


if __name__ == "__main__":
    main(sys.argv[1:])
