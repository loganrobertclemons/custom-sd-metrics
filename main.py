#!/usr/bin/python
# Copyright 2018 Google LLC.
# SPDX-License-Identifier: Apache-2.0

import click
import datetime
import logging
import pycurl
import urlparse
import warnings

from google.api_core.exceptions import GoogleAPIError
from google.cloud import monitoring_v3


_BASE = 'custom.googleapis.com/mymetrics/latency'
_KIND = monitoring_v3.enums.MetricDescriptor.MetricKind.GAUGE
_VALUE_TYPE = monitoring_v3.enums.MetricDescriptor.ValueType.DOUBLE


class LatencyError(Exception):
  pass


def _logging_config(verbose=False):
  level = logging.INFO if verbose else logging.WARNING
  warnings.filterwarnings('ignore', r'.*end user credentials.*', UserWarning)
  logging.basicConfig(level=level)


def _fetch_latency_data(url):
  c = pycurl.Curl()
  c.setopt(pycurl.URL, url)
  c.setopt(pycurl.FOLLOWLOCATION, 1)
  c.setopt(pycurl.WRITEFUNCTION, lambda _: None)
  try:
    c.perform()
  except pycurl.error, e:
    raise LatencyError(e.message, *e.args)
  data = {
      'dns': c.getinfo(pycurl.NAMELOOKUP_TIME),
      'tcp': c.getinfo(pycurl.CONNECT_TIME),
      'ttfb': c.getinfo(pycurl.STARTTRANSFER_TIME),
      'total': c.getinfo(pycurl.TOTAL_TIME),
  }
  c.close()
  return data


def _get_series(metric_type, project_id, label, host, value, dt=None):
  series = monitoring_v3.types.TimeSeries()
  series.metric.type = '/'.join((_BASE, metric_type))
  series.resource.type = 'global'
  series.metric.labels['label'] = label
  series.metric.labels['host'] = host
  point = series.points.add()
  point.value.double_value = value
  point.interval.end_time.FromDatetime(dt or datetime.datetime.utcnow())
  return series


def _add_series(project_id, series, client=None):
  client = client or monitoring_v3.MetricServiceClient()
  project_name = client.project_path(project_id)
  if isinstance(series, monitoring_v3.types.TimeSeries):
    series = [series]
  try:
    client.create_time_series(project_name, series)
  except GoogleAPIError, e:
    raise LatencyError('Error from monitoring API: %s' % e)


@click.command()
@click.option('--project-id', required=True, help='Stackdriver project id')
@click.option('--label', required=True, help='Metric label')
@click.option('--dry-run', default=False, is_flag=True, help='Skip Stackdriver')
@click.option('--verbose', default=False, is_flag=True, help='Verbose logging')
@click.argument('urls', required=True, nargs=-1)
def main(project_id, urls, label, dry_run, verbose):
  _logging_config(verbose)
  logging.info('starting')
  for url in urls:
    logging.info('fetching URL %s', url)
    try:
      data = _fetch_latency_data(url)
      if not dry_run:
        series = []
        for name, value in data.items():
          series.append(_get_series(name, project_id, label,
                                    urlparse.urlsplit(url).netloc, value))
        _add_series(project_id, series)
    except LatencyError, e:
      logging.exception(e)
    else:
      logging.info('data %s', data)


if __name__ == '__main__':
  main(auto_envvar_prefix='MON')