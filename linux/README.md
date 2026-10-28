# Linux – Week 1

Hands-on Linux exercises from the DevOps Experts course, done inside a disposable Ubuntu container (sandbox).

## Environment
### Launching sandbox

```bash
docker run --name devops-sandbox -d ubuntu:latest sleep 10000000
docker exec -it devops-sandbox bash
```
## Assignments

### 1. File System Basics
**Task:**

1.	Create a directory named linux_course in your home directory.
2.	Inside linux_course, create two subdirectories: week1 and week2.
3.	Create a text file named intro.txt inside week1 and write "Welcome to Linux!" into it.

```bash
cd ~
mkdir linux_course
cd linux_course
ls -la
mkdir week1 week2
cd week1
touch intro.txt
echo "Welcome to Linux!" > intro.txt
cat intro.txt
```
### 2. File Permissions
**Task:**

1.	Create a file named private_data in the linux_course/week1 directory.
2.	Change its permissions so that only the file owner can read and write it.
3.	Verify the permissions using ls -l.

```bash
cd ~/linux_course/week1
touch private_data
ls -la
chmod 600 private_data
ls -l
```
### 3. Finding Files
**Task:**

1.	Create three files in linux_course/week2 named file1.txt, file2.txt, and file3.txt.
2.	Use the find command to locate all .txt files in the linux_course directory.

```bash
cd ~/linux_course/week2
touch file1.txt file2.txt file3.txt
ls -la
find ~/linux_course -name "*.txt"
```
### 4. Text Manipulation
**Task:**

Create a file named log.txt in the week2 directory with the following content: 
```
error: Disk space low
info: System rebooted
warning: High memory usage
```
1.	Use grep to find all lines containing the word "error".
2.	Save the output to a file named error.log.

```bash
cd ~/linux_course/week2
echo "error: Disk space low" > log.txt
echo "info: System rebooted" >> log.txt
echo "warning: High memory usage" >> log.txt
cat log.txt
grep "error" log.txt > error.log
cat error.log
```

### 5. Process Monitoring
**Task:**
1.	Start a process in the background using sleep 300.
2.	Use ps to find the sleep process.
3.	Terminate the process using kill.

```bash
sleep 300 &
ps                 # find the PID of "sleep"
kill <PID>
ps                 # sleep is gone
```
### 6. Disk Usage
**Task:**
1.	Use the df command to check the available disk space on your system.
2.	Use the du command to find the size of the linux_course directory.
3.	Save the results to a file named disk_report.txt in the week2 directory.

```bash
cd ~
df -h > linux_course/week2/disk_report.txt
du -sh linux_course >> linux_course/week2/disk_report.txt
cat ~/linux_course/week2/disk_report.txt
```
### 7. Networking
**Task:**
1.	Check your system's current IP address using ip a or ifconfig.
2.	Test the connectivity to google.com using the ping command with 4 packets.
3.	Save the ping output to a file named ping_output.txt in the week2 directory.

```bash
ip a               # container IP: inet 172.17.0.2 on eth0
ping -c 4 google.com > ~/linux_course/week2/ping_output.txt
cat ~/linux_course/week2/ping_output.txt
```
### 8. Shell Scripting
**Task:**
1.	Write a shell script named hello.sh that prints "Hello, Linux!" to the screen.
2.	Make the script executable.
3.	Execute the script and verify the output.

``` bash
cd ~/linux_course
vim hello.sh
cat hello.sh
chmod +x hello.sh
ls -la
./hello.sh
```
### 9. Scheduling Tasks
**Task:**

1.	Use cron to schedule a task that appends the current date and time to a file named timestamp.log in the linux_course directory every minute.
2.	Verify that the task runs correctly by checking the file after a few minutes.

cron does not start automatically in a container, so the service is started manually first.

```bash
cd ~/linux_course
service cron start
crontab -e
# added line (every minute):
# * * * * * TZ=Asia/Jerusalem date >> /root/linux_course/timestamp.log
crontab -l
cat timestamp.log
```

### 10. Archiving and Compression
**Task:**

1.	Archive the linux_course directory into a tar file named linux_course.tar.
2.	Compress the archive using gzip to create linux_course.tar.gz.
3.	Verify the archive's contents without extracting it.

```bash
cd ~
ls -la
tar cvf linux_course.tar linux_course
gzip linux_course.tar
ls
tar -tzvf linux_course.tar.gz
```

### Bonus – SSH to a remote server (SDF)
**Task:** Create an account on sdf.org and connect to `tty.sdf.org` over SSH.

```bash
ssh <username>@tty.sdf.org
ssh -v <username>@tty.sdf.org    # verbose mode, used to debug the first failed logins

# on the remote server:
uname -a                         # NetBSD
```

## Issues & fixes

**`apt update` failed inside the container – "Temporary failure resolving"**
The container inherited the WSL DNS server (`10.255.255.254`), which is not
reachable from inside the Docker network, so package hostnames could not be resolved.
Fix: `echo "nameserver 8.8.8.8" > /etc/resolv.conf`, then `apt update` worked
and I installed the missing tools (`procps`, `iputils-ping`, `iproute2`, `cron`).

**`docker run` failed – "container name already in use"**
After a restart the container was not deleted, only stopped, and `docker run`
tries to create a new container with the same name.
Fix: `docker start devops-sandbox`, then `docker exec -it devops-sandbox bash`.

**SSH to SDF closed right after the password**
`ssh -v` showed that authentication succeeded and the server closed the session
immediately. The new account was not fully activated yet. After a few minutes
the login worked (in a restricted shell, since the account is not validated).
