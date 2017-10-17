import boto3
service_client_list = [
		'ec2',
		'emr',
		'iam',
		's3',
	]

def get_client(service_client):
	if service_client in service_client_list:
		return boto3.client(service_client)
	else:
		return None

def get_resources(service_client, region):
	if service_client in service_client_list:
		return boto3.resource(service_client, region_name=region)
	else:
		return None

def get_regions():
	regions = get_client('ec2').describe_regions()["Regions"]
	return [region['RegionName'] for region in regions]

def get_ec2_instances(region):
	ec2_instances = get_resources('ec2', region)
	return ec2_instances.instances.filter(
		Filters=[{
			'Name': 'instance-state-name',
			'Values':['*']
		}]
	)

def show_ec2_instances():
	for region in get_regions():
		print("###(Region:{})###".format(region))
		for instance in get_ec2_instances(region):
			tags = {t['Key'].lower(): t['Value'] for t in instance.tags} if instance.tags else {}
			instance_state = instance.state['Name']
			instance_name = tags.get('name', 'undefined')
			print("  * {}: {}".format(instance_name, instance_state))

def get_s3_buckets(region):
	s3_instances = get_resources('s3', region)
	return s3_instances.buckets.all()

def show_s3_buckets():
	for region in get_regions():
		print("###Region:({})###".format(region))
		for bucket in get_s3_buckets(region):
			for object in bucket.objects.all():
				print("  * {} : {}".format(bucket.name, object.key))

def show_s3_buckets_acl():
	for region in get_regions():
		print("###Region:({})###".format(region))
		for bucket in get_s3_buckets(region):
			print(" * {}".format(bucket.name))
			for grant in bucket.Acl().grants:
				grantee = grant['Grantee']
				display_name = grantee.get("DisplayName", 'undefined')
				uri = grantee.get("URI", 'undefined')
				permission = grant['Permission']
				if display_name == 'undefined':
					print("   - {}({})".format(uri, permission))
				else:
					print("   - {}({})".format(display_name, permission))

def get_iam_users():
	users = get_client('iam')
	return users.list_users()['Users']

def get_iam_groups(username):
	groups = get_client('iam').list_groups_for_user(UserName=username)
	return groups['Groups']

def get_iam_role_policies(rolename):
	role_policies = get_client('iam').list_role_policies(RoleName=rolename)
	return role_policies['PolicyNames']

def get_iam_roles():
	roles = get_client('iam').list_roles()
	return roles['Roles']

if __name__ == '__main__':
	show_s3_buckets_acl()
