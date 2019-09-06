#fix the sdl2 init error
conda config --add channels conda-forge
conda install sdl2

D2D=1 ./slam.py 
