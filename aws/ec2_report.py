#!/usr/bin/env python3

import boto3
from prettytable import PrettyTable
import argparse
import objectpath
import json
from datetime import datetime, timedelta, date

aws_regions = { 
      "us-east-1":"US East (N. Virginia)",
      "us-east-2":"US East (Ohio)",
      "us-west-1":"US West (N. California)",
      "us-west-2":"US West (Oregon)",
      "ca-central-1":"Canada (Central)",
      "eu-west-1":"EU (Ireland)",
      "eu-central-1":"EU (Frankfurt)",
      "eu-west-2":"EU (London)",
      "ap-northeast-1":"Asia Pacific (Tokyo)",
      "ap-northeast-2":"Asia Pacific (Seoul)",
      "ap-southeast-1":"Asia Pacific (Singapore)",
      "ap-southeast-2":"Asia Pacific (Sydney)",
      "ap-south-1":"Asia Pacific (Mumbai)",
      "sa-east-1":"South America (São Paulo)"
  }   

class ReportTable():

  def __init__(self):
    self.rows = 0
    self.service = ''
    self.table = PrettyTable()
    self.table.align = 'l'

  def add_row(self, instance):
    self.rows += 1
    self.table.add_row(instance)

  def set_field_names(self, field_names):
    self.table.field_names = field_names

  def set_service(self, service):
    self.service = service

  def get_service(self):
    return self.service

  def print_table_ascii(self):
    print("{}: {} running instances".format(
      self.get_service(), self.get_num_rows()
      ))
    print(self.table)

  def print_table_html(self):
    msg = '<html><body>'
    msg += self.table.get_html_string()
    msg += '</body></html>'
    return str(msg)

  def get_num_rows(self):
    return self.rows


def get_running_ec2_instances():
  table = ReportTable()
  field_names = [
      'Region',
      'Name',
      'Type',
      'State',
      #'Private IP',
      'Public IP',
      'Life Time',
      'Owner',
      'Expiry Date',
      'Monthly Price (USD)',
      'Total Price (USD)',
      'Price Date'
      ]
  table.set_field_names(field_names)
  table.set_service("EC2")
  client = boto3.client('ec2')
  regions = client.describe_regions()['Regions']
  for region in regions:
    region_name = region['RegionName']
    ec2 = boto3.resource('ec2', region_name=region['RegionName'])
    # Get information for all running instances
    running_instances = ec2.instances.filter(Filters=[{
                                                      'Name':
                                                      'instance-state-name',
                                                      'Values': ['running']}])
    for instance in running_instances:
      [ price_per_unit, publish_date ] = compute_ec2_price(
          instance.instance_type,
          instance.platform if instance.platform == 'Windows' else 'Linux',
          region_name
          )

      launch_time_hour = total_time_in_hour(instance.launch_time.strftime("%Y-%m-%d %H:%M:%S"))
      monthly_time_hour = monthly_time_in_hour(instance.launch_time.strftime("%Y-%m-%d %H:%M:%S"))
      instanceinfo = []
      tags = {t['Key'].lower(): t['Value'] for t in instance.tags}
      instanceinfo.append(region_name.upper())
      instanceinfo.append(tags.get('name', 'undefined'))
      instanceinfo.append(instance.instance_type.upper())
      instanceinfo.append(instance.state['Name'].upper())
      #instanceinfo.append(instance.private_ip_address)
      instanceinfo.append(instance.public_ip_address)
      instanceinfo.append("{:.2f}Hrs".format(float(launch_time_hour)))
      instanceinfo.append(tags.get('owner', 'undefined'))
      instanceinfo.append(tags.get('expiry', 'undefined'))
      monthly_price = compute_price(
          float(price_per_unit["USD"]),
          monthly_time_hour
          )
      total_price = compute_price(
          float(price_per_unit["USD"]),
          launch_time_hour
          )
      instanceinfo.append("{:.2f}".format(monthly_price))
      instanceinfo.append("{:.2f}".format(total_price))
      instanceinfo.append(publish_date)
      table.add_row(instanceinfo)
  return table

def get_running_rds_instances():
  table = ReportTable()
  field_names = [
      'Region',
      'Name',
      'DB Identifier',
      'DB Type',
      'State',
      'Life Time',
      'Monthly price (USD)',
      'Total price (USD)',
      'Price Date'
      ]
  table.set_field_names(field_names)
  table.set_service("RDS")
  client = boto3.client('ec2')
  regions = client.describe_regions()['Regions']
  for region in regions:
    region_name = region['RegionName']
    rds_client = boto3.client('rds', region_name=region_name)
    running_rds_instances = rds_client.describe_db_instances()['DBInstances']
    for db in running_rds_instances:
      [ price_per_unit, publish_date ] = compute_rds_price(
            db.get('DBInstanceClass'),
            'Multi-AZ' if db.get('MultiAZ') == True else 'Single-AZ',
            'MySQL' if db.get('Engine') == 'mysql' else 'Any',
            region_name
          )
      launch_time_hour = total_time_in_hour(db.get('InstanceCreateTime').strftime("%Y-%m-%d %H:%M:%S"))
      monthly_time_hour = monthly_time_in_hour(db.get('InstanceCreateTime').strftime("%Y-%m-%d %H:%M:%S"))
      instanceinfo = []
      instanceinfo.append(region_name.upper())
      instanceinfo.append(db.get('DBName'))
      instanceinfo.append("{}({})".format(
        db.get('DBInstanceIdentifier'),
        db.get('Engine')
        ))
      instanceinfo.append(db.get('DBInstanceClass', 'undefined').upper())
      instanceinfo.append(db.get('DBInstanceStatus', 'undefined').upper())
      instanceinfo.append("{:.2f}Hrs".format(float(launch_time_hour)))
      monthly_price = compute_price(
          float(price_per_unit["USD"]),
          monthly_time_hour
          )
      total_price = compute_price(
          float(price_per_unit["USD"]),
          launch_time_hour
          )
      instanceinfo.append("{:.2f}".format(monthly_price))
      instanceinfo.append("{:.2f}".format(total_price))
      instanceinfo.append(publish_date)
      table.add_row(instanceinfo)
  return table

def compute_ec2_price(instance_type, platform, region):
  pricing_client = boto3.client('pricing', region_name='us-east-1')
  response = pricing_client.get_products(
      ServiceCode='AmazonEC2',
      MaxResults=100,
      Filters = [
        {'Type': 'TERM_MATCH', 'Field':'termType', 'Value': 'OnDemand'},
        {'Type': 'TERM_MATCH', 'Field':'operatingSystem', 'Value': platform},
        {'Type': 'TERM_MATCH', 'Field':'instanceType', 'Value': instance_type},
        {'Type': 'TERM_MATCH', 'Field':'location', 'Value': aws_regions[region]}
        ]
      )
  [price_info_dump] = response['PriceList']
  price_tree = objectpath.Tree(json.loads(price_info_dump))

  #Getting the latest price publication date
  publish_date = price_tree.execute("$.publicationDate")
  #Getting SKU
  [sku] = price_tree.execute("$.terms.OnDemand")
  #Getting rateCode
  [rateCode] = price_tree.execute("$.terms.OnDemand.'{}'.priceDimensions".format(sku))
  #Getting price_per_hour
  price_per_hour = price_tree.execute(
      "$.terms.OnDemand.'{}'.priceDimensions.'{}'.pricePerUnit".format(sku, rateCode))
  return [price_per_hour, publish_date]

def compute_rds_price(instance_type, deployment, engine, region):
  pricing_client = boto3.client('pricing', region_name='us-east-1')
  response = pricing_client.get_products(
      ServiceCode = 'AmazonRDS',
      MaxResults = 100,
      Filters = [
        {'Type': 'TERM_MATCH', 'Field': 'termType', 'Value': 'OnDemand'},
        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
        {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': deployment},
        {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': aws_regions[region]},
        ]
      )
  [price_info_dump] = response['PriceList']
  price_tree = objectpath.Tree(json.loads(price_info_dump))

  #Getting the latest price publication date
  publish_date = price_tree.execute("$.publicationDate")
  #Getting SKU
  [sku] = price_tree.execute("$.terms.OnDemand")
  #Getting rateCode
  [rateCode] = price_tree.execute("$.terms.OnDemand.'{}'.priceDimensions".format(sku))
  #Getting price_per_hour
  price_per_hour = price_tree.execute(
     "$.terms.OnDemand.'{}'.priceDimensions.'{}'.pricePerUnit".format(sku, rateCode))
  return [price_per_hour, publish_date]

def compute_price(price_per_unit, hour):
  return (float(price_per_unit) * hour)

def total_time_in_hour(launch_time):
  datetimeFormat = '%Y-%m-%d %H:%M:%S'
  diff = datetime.now() - datetime.strptime(launch_time, datetimeFormat)
  day, hour, min = diff.days, diff.seconds//3600, (diff.seconds//60)%60
  return ( day*24 + hour + min/60)

def monthly_time_in_hour(launch_time):
  datetimeFormat = '%Y-%m-%d %H:%M:%S'
  first_day_of_month = "{} 00:00:00".format(date.today().replace(day=1))
  first_day_of_month_datetime = datetime.strptime(first_day_of_month, datetimeFormat)
  launch_datetime = datetime.strptime(launch_time, datetimeFormat)
  diff_hours = float(0)
  if launch_datetime > first_day_of_month_datetime:
    diff_hours = total_time_in_hour(launch_time)
  else:
    diff_day = date.today() - date.today().replace(day=1)
    diff_hours = diff_day.days * 24 + datetime.now().hour + datetime.now().minute/60
  return diff_hours

def send_ses_email(
        to_address, from_address, subject, html_body):
  email_client = boto3.client('ses', region_name='us-east-1')
  return email_client.send_email(
      Source=from_address,
      Destination={
          'ToAddresses': [to_address],
      },
      Message={
          'Subject': {
              'Data': subject,
          },
          'Body': {
              'Html': {
                  'Data': html_body,
              }
          },
      },
  )


if __name__ == '__main__':
  tables = []
  tables.append(get_running_ec2_instances())
  tables.append(get_running_rds_instances())

  parser = argparse.ArgumentParser(
      description='Sends report of active AWS instances')
  parser.add_argument(
      '--ascii',
      help='Prints instances in ascii table format',
      required=False,
      action='store_true')
  args = parser.parse_args()
  for table in tables:
    if args.ascii:
      table.print_table_ascii()
    else:
      if table.get_num_rows() > 0:
        send_ses_email(
          to_address='ec2-users@lynxanalytics.com',
          from_address='ec2-users@lynxanalytics.com',
          subject='%s Instances Report - %s instances running' % (
              table.get_service(), 
              table.get_num_rows()
              ),
          html_body=table.print_table_html()
          )
