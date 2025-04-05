from dataclasses import dataclass
from docker import DockerClient, from_env
from docker.models.containers import Container

DOWNLOAD_PATH = "/home/container/TEMP_DOWNLOAD"
STEAM_CMD_PATH = "/home/container/steamcmd/steamcmd.sh"
STEAM_GUARD_CODE = None
CONTAINER_ID = "xxxxxxxxxx"
DOWNLOAD_RETRIES = 3
MODS_TO_DOWNLOAD: dict[str, str] = {
    "1377912885": "ace_no_medical",
    "2791403093": "better_inventory",
    "1376867375": "ace_interaction_expansion",
    "639837898": "advanced_towing",
    "2909597835": "advanced_sling_loading",
    "2969350304": "ladder_tweak",
    "333310405": "enhanced_movement",
    "1484261993": "enhanced_missile_smoke",
    "450814997": "cba_a3",
    "1334412770": "dual_arms",
    "2886141254": "improved_craters",
    "1808238502": "lambs_suppression",
    "1858075458": "lambs_danger",
    "541888371": "cup_vehicles",
    "497660133": "cup_weapons",
    "497661914": "cup_units",
    "583496184": "cup_terrains_core",
    "583544987": "cup_terrains_maps",
    "2095882226": "better_flares",
    "2260572637": "better_ir",
    "929396506": "mrb_air_visibility",
    "1578884800": "window_breaker",
    "1360202407": "dynamic_view_distance",
    "1808723766": "swim_faster",
    "2129532219": "project_sfx",
    "2095827925": "brighter_flares",
    "2964986025": "tv_guided_missiles",
    "1841047025": "prone_launcher",
    "1105511475": "arma_fpx",
    "2372036642": "backpack_chest",
    "2867537125": "antistasi"
}


@dataclass
class Runtime:
    container: Container
    credentials: list[str]

    def get_download_command(self, mods: list[str], validate = False) -> str:
        credentials = self.credentials
        command = [
            f"{STEAM_CMD_PATH} +force_install_dir {DOWNLOAD_PATH} +login {credentials[0]} {credentials[1]}",
            "" if STEAM_GUARD_CODE is None else f"+set_steam_guard_code {STEAM_GUARD_CODE}"
        ]
        for mod in mods:
            command.append(f"+workshop_download_item 107410 {mod}")

        command.extend(filter(None, [
            ("validate" if validate else ""),
            "+quit"
        ]))
        return " ".join(command)

    @staticmethod
    def from_client(client: DockerClient):

        # Find the target container.
        container = None
        for v in client.containers.list():
            if v.short_id == CONTAINER_ID:
                container = v
                break

        if container is None:
            raise Exception("Could not find container by short ID!")

        # Read steam account credentials.
        with open("credentials.txt", "r") as fp:
            credentials = [line.strip().replace("\n", "") for line in fp.readlines()]

        if len(credentials) != 2:
            raise Exception("There are not two credential sets!")

        # Make sure the mods download directory exists.
        container.exec_run("[ -d /home/container/TEMP_DOWNLOAD ] || mkdir -p /home/container/TEMP_DOWNLOAD")
        return Runtime(container, credentials)


def directory_exists(runtime: Runtime, dir_path: str) -> bool:
    return runtime.container.exec_run(f"test -d '{dir_path}'", demux=True).exit_code == 0


def download_mods(runtime: Runtime, mods: list[str]):
    command = runtime.get_download_command(mods, False)
    print(command)

    # Run the download command, streaming stdout.
    result = runtime.container.exec_run(command, stream=True)
    logs = []
    for line in result.output:
        decoded = line.decode("utf-8")
        if decoded:
            print(decoded.replace("\n", ""))
            logs.append(decoded)

    return


def move_mod(runtime: Runtime, mod_path: str, dest_path: str) -> bool:

    # Move from workshop content dir to main mod dir (base path).
    commands = [
        f"mkdir -p \"{dest_path}\"",
        f"bash -c \"mv \'{mod_path}\'/* \'{dest_path}\'\""
    ]

    # Run each command, making sure they're successful.
    for command in commands:
        exit_code = runtime.container.exec_run(command).exit_code
        if exit_code != 0:
            print(f"!! Got exit status '{exit_code}' running: {command}")
            return False

    return True


def main() -> None:
    runtime = Runtime.from_client(from_env())

    missing_ids, dest_paths = [], {}
    for mod, name in MODS_TO_DOWNLOAD.items():

        # Test to see which mods exist.
        dest_path = "/home/container/@" + name.strip().lower()
        if directory_exists(runtime, dest_path):
            continue

        missing_ids.append(mod)
        dest_paths[mod] = dest_path
        print(f"Missing mod: {name}")

    if len(missing_ids) > 0:

        print("Started downloading mods!")
        download_mods(runtime, missing_ids)
        for mod in missing_ids:

            name = MODS_TO_DOWNLOAD[mod]
            mod_path = f"{DOWNLOAD_PATH}/steamapps/workshop/content/107410/{mod}"
            if not directory_exists(runtime, mod_path):
                print(f"Failed to download mod: {name}")
                continue

            print(f"Successfully downloaded mod: {name}")
            if move_mod(runtime, mod_path, dest_paths[mod]):
                print(f"Failed to move mod: {name}")

            else:
                print(f"Successfully moved mod: {name}")

    # Generate mod string.
    print(";".join(["@" + name for name in MODS_TO_DOWNLOAD.values()]))
    print("Finished.")


if __name__ == "__main__":
    main()
