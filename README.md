# AUTO-BINANCE-TELEGRAM


It is recommended to use Python virtual environment to isolate the packages required for this repository, thus, avoiding any dependency issues. Plus it keeps the system packages clean. Use the following command to create a new virtual environment (here we're calling it venv).
```
python -m venv venv
```
This will create a new directory named `venv`. This directory is already included in `.gitignore`. If you mean to use some other name for your virtual environment, please don't forget to add it to `.gitignore` otherwise the whole junk in that folder will be added to git. We now need to activate the environment.
```
source venv/bin/activate
```
If everything done correctly, we will see `(venv)` on the left side of terminal prompt. This indicates that our virtual environment is now activated. We can proceed with installation of required packages. Also keep in mind that trying to install packages without activating virtual environment will add packages to system Python, which certainly kills the purpose of virtual environment.