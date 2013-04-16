#/bin/bash
cd /root/

# apt packages
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -q -y install mysql-server git subversion build-essentials {additional_packages}

# config git
git config --global user.name "{gituser}"
git config --global user.email "{gitemail}"

# mysql db/dbuser setup
mysql -uroot -e "UPDATE mysql.user SET Password=PASSWORD('{{mysql_password}}') WHERE User='root';
FLUSH PRIVILEGES;"

# passwordless mysql
echo "[client]
    user = root
    password = {{mysql_password}}" > /root/.my.cnf

# ssh keys
[ -d "/root/.ssh" ] || mkdir /root/.ssh
echo "{private}" > /root/.ssh/id_rsa
chmod 600 /root/.ssh/id_rsa
echo "{public}" > /root/.ssh/id_rsa.pub
echo "{authorized_keys}" >> /root/.ssh/authorized_keys
echo "{known_hosts}" >> /root/.ssh/known_hosts

