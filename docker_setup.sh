#Connect to the server: 
ssh -p 6543 matteo_cancian@samuel-daros.it
#Navigate to the project folder:
cd docker_CoC
#Activate the virtual environment:
python3 venv/bin/activate env
#Pull the latest version of the project:
git pull https://github.com/CancianMatteo/CoC_Clan_Manager.git
#Build the docker image:
sudo docker build -t python-coc-app .
#Create the container:
sudo docker container create --name CoC-py-script python-coc-app:latest
#Start the container:
sudo docker container start CoC-py-script

screen
#Check the logs:
sudo docker container ls -a
sudo docker logs CoC-py-script

#Stop and remove the container:
sudo docker container stop CoC-py-script
sudo docker container remove CoC-py-script