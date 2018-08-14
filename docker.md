# 使用 Docker 编译 Python 源码

- 项目目录结构

    - python_source_code_study
        - build      # build 目录，即 configure --prefix
        - Python-2.5 # 源码


- Dockerfile

```
FROM ubuntu
RUN apt-get install -y gcc make vim
```

- build image

`docker build -t ubuntu:pyc .`

- run ubuntu:pyc

`docker run -it --name ubuntu_pyc -v /Users/jiaminlu/Workspace/python/python_source_code_study:/data/python_source_code_study ubuntu:latest`

- 编译 Python

```
cd /data/python_source_code_study/Pyhton-2.5
./configure --prefix /data/python_source_code_study/build
```