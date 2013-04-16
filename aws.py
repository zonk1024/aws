#!/usr/bin/env python

from boto import ec2
from pprint import pformat
from time import time, sleep
from fabric.api import env, put, sudo, run, execute
from os import chmod, listdir, mkdir
from os.path import isdir
from deploy_settings import settings

api_key=settings['api_key']
secret_key=settings['secret_key']
script_template=settings['script_template']
debug = settings['debug']

con = ec2.connect_to_region('us-east-1',
                            aws_access_key_id = api_key,
                            aws_secret_access_key = secret_key)

def genLocalKeys():
    """
         Retruns a dict with a private key and a public key.
         Kind of dirty, but crypto's exportKey('OpenSSH') is broken.
    """
    from Crypto.PublicKey import RSA
    from subprocess import check_output
    from os import remove
    key = RSA.generate(4096)
    pri = key.exportKey()
    pub = key.publickey().exportKey()
    with open('public-key', 'w') as public:
        public.write(pub)
    sshpub = check_output('ssh-keygen -m PKCS8 -f public-key -i'.split(' '))
    remove('public-key')
    return {'private': pri, 'public': sshpub}

def genEC2Keypair(connection, key_name):
    keypair = connection.create_key_pair(key_name)
    if debug: print(keypair)
    if debug: print(dir(keypair))
    keypair.save('keys')
    return keypair

def findOrGenEC2Keypair(connection):
    if not isdir('keys'):
        mkdir('keys')
    local = [i[:-4] for i in listdir('keys') if i[-4:]=='.pem']
    common = [i for i in connection.get_all_key_pairs() if str(i.name) in local]
    if common:
        return common[0]
    return genEC2Keypair(connection, str(int(time()*1000)))

def pluckPubKeys():
    from os import listdir
    from os.path import expanduser
    ssh_pub_key_files = [k for k in listdir(expanduser('~') + '/.ssh/') if k[-4:]=='.pub']
    ssh_pub_keys = ''
    for k in ssh_pub_key_files:
        with open(expanduser('~') + '/.ssh/' + k, 'r') as pub_key:
            ssh_pub_keys += pub_key.readline().strip() + '\n'
    if debug: print('Your public key(s) are:\n{}\n'.format(ssh_pub_keys))
    return ssh_pub_keys

def printInstances(connection):
    inst = con.get_all_instances()
    print('Running instances: {}\n'.format(pformat(inst)))

def genScript(template_settings):
    with open(script_template, 'r') as template:
        out = template.read().format(**template_settings)
    if debug: print out
    with open('deploy.sh', 'w') as deploy:
        deploy.write(out)
    chmod('deploy.sh', 0770)
    return out

def spinInstance(connection, ami_name, key, size='t1.micro', sec_grps=['basicweb'], shutdown='terminate'):
    image = connection.get_image(ami_name)
    if debug: print('{}\n'.format(image))
    reservation = image.run(instance_initiated_shutdown_behavior=shutdown,
                            security_groups=sec_grps,
                            key_name=key,
                            instance_type=size)
    return reservation.instances[0]

def addKeyToRepo():
    run('echo "{}" >> ~/.ssh/authorized_keys'.format(settings['public']))

def doAddKeyToRepo():
    execute(addKeyToRepo, hosts=['{}@{}'.format(settings['repouser'], settings['repo'])])

def build():
    put('deploy.sh', '~', mirror_local_mode=True)
    sudo('su -l -c "/home/ubuntu/deploy.sh" root | tee deploy.out')

def doBuild():
    env.key_filename = 'keys/' + EC2Keypair.name + '.pem'
    execute(build, hosts=['ubuntu@' + instance.ip_address])


print('Creating keypair for new instance.')
settings.update(genLocalKeys())
print('Finding or creating keypair to connect to instance.')
EC2Keypair = findOrGenEC2Keypair(con)
print('Grabbing your public keys')
settings['authorized_keys'] = pluckPubKeys()
print('Generating, stashing, and chmod-ing deployment script.')
script = genScript(settings)
print('Spinning new instance of image \'{}\''.format(settings['image']))
instance = spinInstance(con, settings['image'], EC2Keypair.name)
print('Waiting for state to change from \'pending\'...')
while instance.update() == u'pending':
    sleep(5)
    print('Almost...')
print('There we are!')
print('Spun instance with public IP of: {}'.format(instance.ip_address))
print('Sleeping for 30 seconds to make sure ssh is ready.')
sleep(30)
doAddKeyToRepo()
doBuild()

