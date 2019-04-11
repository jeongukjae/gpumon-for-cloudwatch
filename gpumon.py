import requests
import boto3
import argparse

from pynvml import (nvmlInit, nvmlDeviceGetCount, nvmlShutdown,
                    nvmlDeviceGetHandleByIndex, nvmlDeviceGetPowerUsage,
                    nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU,
                    nvmlDeviceGetUtilizationRates, NVMLError)
from datetime import datetime
from time import sleep

BASE_URL = 'http://169.254.169.254/latest/meta-data/'
parser = argparse.ArgumentParser()
parser.add_argument(
    '-i',
    '--interval',
    dest='interval',
    default=10,
    type=int,
    help='sleep interval (times between collecting each metrics)')
parser.add_argument(
    '-l',
    '--log-path',
    dest='log_path',
    default='/tmp/gpumon_stats',
    type=str,
    help='path of gpumon logs (/tmp/stat will be /tmp/stats-2019-01-01T20)')
parser.add_argument('-r',
                    '--resolution',
                    dest='resolution',
                    default=60,
                    type=int,
                    help='resolution of storage in cloudwatch')
parser.add_argument('--namespace',
                    dest='namespace',
                    default='DeepLearning',
                    type=str,
                    help='namespace of cloudwatch (default: DeepLearning)')


def _get_cloudwatch_meta(instance_id, image_id, instance_type, gpu_number):
    return [{
        'Name': 'InstanceId',
        'Value': instance_id
    }, {
        'Name': 'ImageId',
        'Value': image_id
    }, {
        'Name': 'InstanceType',
        'Value': instance_type
    }, {
        'Name': 'GPUNumber',
        'Value': gpu_number
    }]


def _format_metric(name, value, resolution, dimension, unit='None'):
    return {
        'MetricName': name,
        'Dimensions': dimension,
        'Unit': unit,
        'StorageResolution': resolution,
        'Value': value
    }


def _put_log(string, file_path):
    with open(file_path, 'a+') as f:
        f.write(string)


def _get_meta_data(meta_type):
    return requests.get(BASE_URL + meta_type).text


def get_gpu_power(handle):
    """get device power usage
    """

    return nvmlDeviceGetPowerUsage(handle) / 1000.0


def get_gpu_temperature(handle):
    """get current temperature of gpu
    """

    return nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)


def get_gpu_utilization(handle):
    """return utilization of gpu (including memory utilization)
    """

    return nvmlDeviceGetUtilizationRates(handle)


def put_metrics_to_log_file(gpu_num, power, temp, utilization, log_path):
    """put metric line into log file
    """
    try:
        _put_log(
            "gpu %d, gpu util: %s, mem util: %s, power usage: %s, temp: %s\n" %
            (gpu_num, utilization.gpu, utilization.memory, power, temp),
            log_path)
    except Exception as e:
        print("Cannot print to %s, %s" % (log_path, e))


def put_metrics_to_cloudwatch(gpu_num, power, temp, utilization, resolution,
                              cloudwatch, namespace, instance_meta):
    dimension = _get_cloudwatch_meta(
        instance_id=instance_meta['instance_id'],
        image_id=instance_meta['image_id'],
        instance_type=instance_meta['instance_type'],
        gpu_number=gpu_num)

    cloudwatch.put_metric_data(MetricData=[
        _format_metric('GPU Usage', utilization.gpu, resolution, dimension,
                       'Percent'),
        _format_metric('Memory Usage', utilization.memory, resolution,
                       dimension, 'Percent'),
        _format_metric('Power Usage (Watts)', power, resolution, dimension),
        _format_metric('Temperature (C)', temp, resolution, dimension,
                       'Percent'),
    ],
                               Namespace=namespace)


def main():
    args = parser.parse_args()

    nvmlInit()

    num_device = list(range(nvmlDeviceGetCount()))
    log_path = args.log_path + datetime.now().strftime('%Y-%m-%dT%H')

    instance_meta = {
        'instance_id': _get_meta_data('instance-id'),
        'image_id': _get_meta_data('ami-id'),
        'instance_type': _get_meta_data('instance-type'),
        'region': _get_meta_data('placement/availability-zone')[:-1]
    }

    cloudwatch = boto3.client('cloudwatch',
                              region_name=instance_meta['region'])
    try:
        while True:
            for gpu_num in num_device:
                put_metric = True
                handle = nvmlDeviceGetHandleByIndex(gpu_num)

                try:
                    power = get_gpu_power(handle)
                    temp = get_gpu_temperature(handle)
                    utilization = get_gpu_utilization(handle)
                except NVMLError as error:
                    _put_log("cannot collect metrics", log_path)
                    put_metric = False

                if put_metric:
                    put_metrics_to_log_file(gpu_num, power, temp, utilization,
                                            log_path)
                    put_metrics_to_cloudwatch(gpu_num=gpu_num,
                                              power=power,
                                              temp=temp,
                                              utilization=utilization,
                                              resolution=args.resolution,
                                              cloudwatch=cloudwatch,
                                              namespace=args.namespace,
                                              instance_meta=instance_meta)

            sleep(args.interval)
    finally:
        nvmlShutdown()


if __name__ == "__main__":
    main()
