#!/usr/bin/python3

from docker import Client
import json, requests, sys

sys.path.append("/root/hubops")
from config.docker_config import docker_config
from sys import argv
from random import randint


class ContainerClass:
    def __init__(self):
        self.name = "hubops{}".format(randint(100000, 999999))
        self.hostname = self.name

    def host_config_defaults(self):
        port_bindings = {22: 4022}
        dns = ["8.8.8.8", "8.8.4.4"]
        # network_mode = 'host'
        # mem_limit = "512m"
        # memswap_limit = "700m"
        # command = "/bin/bash"
        privileged = True
        return locals()

    def host_config_variables(self, **kwargs):
        host_config_dict = self.host_config_defaults()
        del host_config_dict["self"]

        for config_param, config_value in kwargs.items():
            host_config_dict.update({config_param: config_value})

        return host_config_dict


def get_image_remote(client_instance, image_repository, image_repository_tags):
    # User wants official or unofficial images?
    while True:
        official_or_not = input("Search for official images or unofficial images?\n"
                                "Official(O)\n"
                                "Unofficial(U)\n").lower()
        if official_or_not in list("ou"):
            break

    found_list = search_images_name_remote(image_repository, client_instance, official_or_not)

    if len(found_list) == 1:
        print("No official image found for {}".format(image_repository))
    else:
        print("Official images on Docker Hub:")
        for official_name in found_list[1:]:
            print("{}. {}".format(found_list.index(official_name), official_name))

        while True:
            try:
                image_index_to_pull = int(input("\nWhich image would you like to work on from the above list?\n"
                                                "Enter the number which appears with the image name.\n"
                                                "e.g. If you want to pull\n"
                                                "3. tomcat7\n"
                                                "Then type in 3 and press the Enter key.\n"))
                image_name_to_pull = found_list[image_index_to_pull]
                break

            except (IndexError, ValueError):
                pass

        image_tags = list([''])
        image_tags_request = requests.get(
            "https://registry.hub.docker.com/v1/repositories/{}/tags".format(image_name_to_pull))
        for image_tag_details in image_tags_request.json():
            image_tags.append(image_tag_details['name'])

        print("\n\nThe tags available for {} on Docker Hub are:\n".format(image_name_to_pull))
        for tag_name in image_tags[1:]:
            print("{}. {}".format(image_tags.index(tag_name), tag_name))

        print("\n")

        if image_repository_tags in image_tags[1:]:
            print("Found specified {} tag in the available tags.".format(image_repository_tags))
            image_tag_to_pull = image_repository_tags
        else:
            print("Could not find {} tag in the available tags.\n"
                  "Which {} tag do you want to work with?\n".format(image_repository_tags, image_name_to_pull))

            while True:
                try:
                    tag_input = int(input())
                    image_tag_to_pull = image_tags[tag_input]
                    break
                except (IndexError, ValueError):
                    print("Enter a valid tag number!")
                    pass

        image_to_pull = "{}:{}".format(image_name_to_pull, image_tag_to_pull)
        print("Pulling {} now...".format(image_to_pull))
        pull_process(image_to_pull, client_instance)


def search_images_local(opened_client, user_repotag):
    local_repotags = list()
    for image_name in opened_client.images():
        for separate_tags in image_name['RepoTags']:
            local_repotags.append(separate_tags)

    if user_repotag in local_repotags:
        return True
    else:
        return False


def search_images_name_remote(name_to_search, opened_client, controller_official):
    hub_results = opened_client.search(name_to_search)
    found_list = list([''])
    for filtered_results in hub_results:
        if (controller_official == "o") and (filtered_results['is_official']):
            print("Found {}".format(filtered_results['name']))
            found_list.append(filtered_results['name'])
        elif controller_official == "u":
            print("Found {}".format(filtered_results['name']))
            found_list.append(filtered_results['name'])
    return found_list


def pull_process(image_to_pull, opened_client):
    for pull_progress in opened_client.pull(image_to_pull, stream=True):
        for pull_element, pull_key in json.loads(pull_progress.decode()).items():
            if pull_element == 'id':
                print("For image id {}:".format(pull_key.lower()))
            if pull_element == 'status':
                print("The current status is {}".format(pull_key.lower()))


def start_container(opened_client, container_up):
    container_object = ContainerClass()
    host_config_dict_var = container_object.host_config_variables()
    host_config_dict = dict()

    for param, value in host_config_dict_var.items():
        # exec(param + '=value')
        host_config_dict.update(opened_client.create_host_config(**host_config_dict_var))

    container = opened_client.create_container(image=container_up,
                                               name=container_object.name,
                                               hostname=container_object.hostname,
                                               entrypoint="/bin/bash",
                                               stdin_open=True,
                                               tty=True,
                                               ports=[22],
                                               host_config=host_config_dict)

    container_id = container['Id']
    print("Container with ID {} has been created.".format(container_id))

    if container['Warnings'] is None:
        print("The container was created with no warnings.")
    else:
        print("These warning(s) popped up while creating the container.\n{}".format(container['Warnings']))

    print("Starting container {}.".format(container_object.name))
    opened_client.start(container= container_id)


def foreground_process(image_repository, image_repository_tags):
    # Establishing connection
    client_instance = Client(base_url=docker_config())

    user_repotag = "{}:{}".format(image_repository, image_repository_tags)

    # Searching for images locally
    local_exists = search_images_local(client_instance, user_repotag)

    if local_exists:
        print("Found the image {} locally, proceeding now.".format(user_repotag))
    elif not local_exists:
        print("The image does not exist locally.\n"
              "HubOps will now search for images on Docker Hub.\n")
        get_image_remote(client_instance, image_repository, image_repository_tags)

    print("Setting up the container now...")
    start_container(client_instance, user_repotag)


if __name__ == '__main__':
    try:
        image_name_argv = argv[1]
    except IndexError:
        image_name_argv = "centos"
        print("No image name entered. Setting {} by default.".format(image_name_argv))

    try:
        image_tag_argv = argv[2]
    except IndexError:
        image_tag_argv = "latest"
        print("No image tag entered. Setting {} by default.".format(image_tag_argv))

    foreground_process(image_name_argv, image_tag_argv)
