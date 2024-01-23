import json
import os
import subprocess


def prepare_env(platform: str, config: json, select_config: str = None):
    if platform != "gha" and platform != "azp":
        raise ValueError("Only GitHub Actions and Azure Pipelines is supported at this point.")

    if platform != "azp" and select_config is not None:
        raise ValueError("The --select-config parameter can only be used with Azure Pipelines.")

    if select_config:
        config = config[select_config]

    def _set_env_variable(var_name: str, value: str):
        print("{} = {}".format(var_name, value))
        os.environ[var_name] = value
        if platform == "gha":
            if compiler in ["VISUAL", "MSVC"]:
                os.system('echo {}={}>> {}'.format(var_name, value, os.getenv("GITHUB_ENV")))
            else:
                subprocess.run(
                    'echo "{}={}" >> $GITHUB_ENV'.format(var_name, value),
                    shell=True
                )

        if platform == "azp":
            if compiler in ["VISUAL", "MSVC"]:
                subprocess.run(
                    'echo ##vso[task.setvariable variable={}]{}'.format(var_name, value),
                    shell=True
                )
            else:
                subprocess.run(
                    'echo "##vso[task.setvariable variable={}]{}"'.format(var_name, value),
                    shell=True
                )

    compiler = config["compiler"]
    compiler_version = config["version"]
    docker_image = config.get("dockerImage", "")
    build_type = config.get("buildType", "")
    xcode_dir = config.get("xcodeDir", "")

    _set_env_variable("BPT_CWD", config["cwd"])
    _set_env_variable("CONAN_VERSION", config["recipe_version"])

    if compiler == "APPLE_CLANG":
        if "." not in compiler_version:
            compiler_version = "{}.0".format(compiler_version)

    _set_env_variable("CONAN_{}_VERSIONS".format(compiler), compiler_version)

    if compiler == "GCC" or compiler == "CLANG":
        if docker_image == "":
            compiler_lower = compiler.lower()
            version_without_dot = compiler_version.replace(".", "")
            image_suffix = ""
            # Use "modern" CDT containers for newer compilers
            if (compiler == "GCC" and float(compiler_version) >= 11) or \
                    (compiler == "CLANG" and float(compiler_version) >= 10):
                image_suffix = "-ubuntu18.04"

            docker_image = "conanio/{}{}{}".format(compiler_lower, version_without_dot, image_suffix)
        _set_env_variable("CONAN_DOCKER_IMAGE", docker_image)

    if build_type != "":
        _set_env_variable("CONAN_BUILD_TYPES", build_type)

    if platform == "gha" or platform == "azp":
        if compiler == "APPLE_CLANG":
            if not xcode_dir:
                xcode_mapping = {
                    "11.0": "/Applications/Xcode_11.7.app",
                    "12.0": "/Applications/Xcode_12.4.app",
                    "13.0": "/Applications/Xcode_13.2.1.app",  # Highest for macos-11 (and default)
                    "13.1": "/Applications/Xcode_13.4.1.app",
                    "14.0": "/Applications/Xcode_14.2.app",  # Highest for macos-12 (default for macos-12 and macos-13)
                    "15.0": "/Applications/Xcode_15.2.app",  # only on macos-13
                }
                if compiler_version in xcode_mapping:
                    xcode_dir = xcode_mapping[compiler_version]
            if xcode_dir:
                subprocess.run(
                    'sudo xcode-select -switch "{}"'.format(xcode_dir),
                    shell=True
                )
                print('executing: xcode-select -switch "{}"'.format(xcode_dir))

            subprocess.run(
                'clang++ --version',
                shell=True
            )

        if compiler in ["VISUAL", "MSVC"]:
            with open(os.path.join(os.path.dirname(__file__), "prepare_env_azp_windows.ps1"), "r") as file:
                content = file.read()
                file.close()

            with open("execute.ps1", "w", encoding="utf-8") as file:
                file.write(content)
                file.close()

            subprocess.run("pip install --upgrade cmake", shell=True, check=True)
            subprocess.run("powershell -file {}".format(os.path.join(os.getcwd(), "execute.ps1")), shell=True, check=True)

    if platform == "gha" and (compiler == "GCC" or compiler == "CLANG"):
        subprocess.run('docker system prune --all --force --volumes', shell=True)
        subprocess.run('sudo rm -rf "/usr/local/share/boost"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/CodeQL"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/Ruby"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/boost"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/go"', shell=True)
        subprocess.run('sudo rm -rf "$AGENT_TOOLSDIRECTORY/node"', shell=True)

    subprocess.run("conan user", shell=True)
