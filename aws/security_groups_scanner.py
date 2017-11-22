#!/usr/bin/env python3
import boto3


def scan_ec2_security_groups():
    membership = {}
    hazard_sg = {}
    regions = boto3.client('ec2').describe_regions()['Regions']
    for region in regions:
        region_name = region['RegionName']
        print("* Region Name: {}".format(region_name))

        ec2 = boto3.resource('ec2', region_name=region['RegionName'])
        running_instances = ec2.instances.filter(Filters=[{
            'Name': 'instance-state-name',
            'Values': ['running', 'stopped']}])
        for instance in running_instances:
            tags = {t['Key'].lower(): t['Value']
                    for t in instance.tags} if instance.tags else {}
            instance_state = instance.state['Name']
            instance_name = tags.get('name', 'undefined')
            instance_key_name = instance.key_name

            for sg in instance.security_groups:
                security_groupid = sg['GroupId']
                security_groupname = sg['GroupName']
                print(
                    "  + {}({}) with key:{} is using security groups: {}({})".format(
                        instance_name,
                        instance_state,
                        instance_key_name,
                        security_groupname,
                        security_groupid))
                membership[instance_name] = security_groupid

        for sg in boto3.client('ec2', region_name=region_name).describe_security_groups()[
                'SecurityGroups']:
            security_groupname = sg['GroupName']
            security_groupid = sg['GroupId']

            if security_groupid in membership.values():
                print("  - {}({}): Used".format(security_groupname, security_groupid))
            else:
                if security_groupname == "default":
                    print(
                        "  - {}({}): skipped unused".format(security_groupname, security_groupid))
                else:
                    print(
                        "  - {}({}): Unused".format(security_groupname, security_groupid))

            for sg_item in sg['IpPermissions']:
                if sg_item['IpProtocol'] == 'tcp':
                    sg_item_from_port = sg_item['FromPort']
                    sg_item_to_port = sg_item['ToPort']
                    sg_item_ip_range = sg_item['IpRanges']
                    if sg_item_from_port == 0 and sg_item_to_port > 0 and len(
                            sg_item_ip_range):
                        for cidr_ip in sg_item_ip_range:
                            if '0.0.0.0/0' in cidr_ip.values():
                                hazard_sg[security_groupid] = security_groupname
                                print(
                                    "    (!!) WARNING Port TCP ({}-{}): {}".format(
                                        sg_item_from_port, sg_item_to_port, sg_item_ip_range))
                            else:
                                print(
                                    "    (*) Port TCP ({}-{}): {}".format(
                                        sg_item_from_port,
                                        sg_item_to_port,
                                        sg_item_ip_range))
                    else:
                        print("    (*) Port TCP ({}-{}): {}".format(sg_item_from_port,
                                                                    sg_item_to_port, sg_item_ip_range))


if __name__ == '__main__':
    scan_ec2_security_groups()
