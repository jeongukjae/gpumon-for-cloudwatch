FROM nvidia/cuda:10.1-runtime

RUN apt-get -qq update && \
    apt-get install -qq -y software-properties-common curl git && \
    add-apt-repository -y ppa:jonathonf/python-3.6 && \
    apt-get -qq update && \
    apt-get install -qq -y build-essential python3.6 python3.6-dev python3-pip && \
    ln -s /usr/bin/python3.6 /usr/bin/python && \
    python -m pip install --no-cache-dir boto3 nvidia-ml-py3 requests

COPY gpumon.py gpumon.py

ENV interval 10
ENV log_path /tmp/gpumon_stats
ENV resolution 60
ENV namespace DeepLearning

CMD python gpumon.py -i ${interval} -l ${log_path} -r ${resolution} -n ${namespace}
