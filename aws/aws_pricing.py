import boto3
import json
import objectpath
from datetime import datetime, timedelta, date


def get_price_running_instances():
    aws_regions = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "ca-central-1": "Canada (Central)",
        "eu-west-1": "EU (Ireland)",
        "eu-central-1": "EU (Frankfurt)",
        "eu-west-2": "EU (London)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
        "ap-northeast-2": "Asia Pacific (Seoul)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-southeast-2": "Asia Pacific (Sydney)",
        "ap-south-1": "Asia Pacific (Mumbai)",
        "sa-east-1": "South America (São Paulo)"
    }

    estimated_monthly_price = 0
    accumulated_total_price = 0
    ec2_client = boto3.client('ec2', region_name='us-east-1')
    regions = ec2_client.describe_regions()['Regions']
    for region in regions:
        region_name = region['RegionName']
        ec2 = boto3.resource('ec2', region_name=region_name)
        running_ec2_instances = ec2.instances.filter(
            Filters=[{
                'Name': 'instance-state-name',
                'Values': ['running']
            }]
        )
        for instance in running_ec2_instances:
            tags = {t['Key'].lower(): t['Value']
                    for t in instance.tags} if instance.tags else {}
            instance_name = tags.get('name', 'undefined')
            instance_type = instance.instance_type.lower()
            launch_time = instance.launch_time.strftime("%Y-%m-%d %H:%M:%S")
            print("{}: {} {} {}".format(
                aws_regions[region_name.lower()], instance_name, instance_type, launch_time))
            priceph = get_instance_pricing(
                instance_type, aws_regions[region_name.lower()])
            total_price = float(priceph.get('USD', 0)) * \
                total_time_in_hours(launch_time)
            monthly_price = float(priceph.get('USD', 0)) * \
                monthly_used_in_hours()
            print(
                " * Total accumulated price in USD: {0:.2f}".format(total_price))
            print(
                " * Monthly charged price in USD: {0:.2f}".format(monthly_price))
            estimated_monthly_price += monthly_price
            accumulated_total_price += total_price
    print(
        "** Total monthly price for all instances in USD: {0:.2f}".format(estimated_monthly_price))
    print(
        "** Total accumulated price for all instances in USD: {0:.2f}".format(accumulated_total_price))


def monthly_used_in_hours():
    diff_day = date.today() - date.today().replace(day=1)
    diff_hours = diff_day.days * 24 + datetime.now().hour + datetime.now().minute / 60
    return diff_hours


def total_time_in_hours(launch_time):
    datetimeFormat = '%Y-%m-%d %H:%M:%S'
    diff = datetime.now() - datetime.strptime(launch_time, datetimeFormat)
    day, hour, min = diff.days, diff.seconds // 3600, (diff.seconds // 60) % 60
    return (day * 24 + hour + min / 60)


def get_instance_pricing(instance_type, region_name):
    pricing = boto3.client('pricing', region_name='us-east-1')
    response = pricing.get_products(
        ServiceCode='AmazonEC2',
        Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name}
        ],
        MaxResults=100
    )

    [price_info_dump] = response['PriceList']
    price_tree = objectpath.Tree(json.loads(price_info_dump))
    publish_date = price_tree.execute("$.publicationDate")
    [sku] = price_tree.execute("$.terms.OnDemand")
    [rateCode] = price_tree.execute(
        "$.terms.OnDemand.'{}'.priceDimensions".format(sku))
    price_per_hours = price_tree.execute(
        "$.terms.OnDemand.'{}'.priceDimensions.'{}'.pricePerUnit".format(
            sku, rateCode))
    print(" * Price OnDemand {} effective from {}: {} USD/hour".format(
        instance_type,
        publish_date,
        price_per_hours["USD"]
    ))
    return price_per_hours


if __name__ == '__main__':
    get_price_running_instances()
