import subprocess
import sys
import getopt
import datetime, time
from pprint import pprint as pp


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
    snapshots_all=[snapshot for snapshot in run_command(APTLY_EXEC+ " snapshot list -raw") if '_'.join(snapshot.split('_')[0:2]) == ARGS['PUBLISH']+'_'+ARGS['DIST']]
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
        

def aptly_update_mirrors(force=False):
    snapshots_without_timestamp=['_'.join(snapshot.split('_')[0:-1]) for snapshot in run_command(APTLY_EXEC+ " snapshot list -raw")]
    for component in ARGS['COMPONENTS']:
        if ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component not in snapshots_without_timestamp or force:
            run_command(APTLY_EXEC+" mirror update "+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component)
            run_command(APTLY_EXEC+" snapshot create "+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component+'_'+TIMESTAMP+' from mirror '+ARGS['PUBLISH']+'_'+ARGS['DIST']+'_'+component)
    

def aptly_publish():
    snapshots_map=create_snapshots_map()
    published=run_command(APTLY_EXEC+" publish list")
    print published
    pp(snapshots_map)
    for timestamp, items in snapshots_map.items():
        for dist,snapshots in items.items():
            temp_s1=""
            temp_s2=","*(len(snapshots)-1)
            for snapshot in snapshots:
                if '['+snapshot+']:' in published:
                    print "snapshot {} is already published".format(snapshot)
                    break
                temp_s1+=snapshot+" "
            if temp_s1:
                run_command(APTLY_EXEC+" publish snapshot -component="+temp_s2+" -distribution="+dist+" "+temp_s1+" "+ARGS['PUBLISH']+'/'+timestamp)

def aptly_housekeep(keep):
    published_snapshots=run_command(APTLY_EXEC+ " publish list -raw")
    indices=[index for index in range(0,len(published_snapshots),2) if published_snapshots[index+1] == ARGS['DIST']]
    sorted_timestamps=sorted([published_snapshots[index] for index in indices])[:len(indices)-keep]
    for timestamp in sorted_timestamps:
        run_command(APTLY_EXEC+ " publish drop "+ARGS['DIST']+" "+timestamp)
    aptly_delete_unpublished_snapshots()
    aptly_delete_unpublished_mirrors()

def aptly_delete_unpublished_snapshots():
    published_snaps=run_command(APTLY_EXEC+ " publish list")  
    snapshots_all=run_command(APTLY_EXEC+" snapshot list -raw")
    for snaps in snapshots_all:
        if '['+snaps+']:' not in published_snaps:
            run_command(APTLY_EXEC+" snapshot drop "+snaps)


def aptly_delete_unpublished_mirrors():
    published_mirrors=run_command(APTLY_EXEC+ " publish list")
    mirrors_all=run_command(APTLY_EXEC+ " mirror list -raw")
    for mirrors in mirrors_all:
        if '['+mirrors+']:' not in published_mirrors:
            run_command(APTLY_EXEC+ " mirror drop "+mirrors)
    
          
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
        aptly_publish()
    #    aptly_housekeep(int(ARGS['KEEP']))
    except BaseException:
        raise


if __name__ == "__main__":
    main(sys.argv[1:])
