# <a id='py-install'></a>python installation instructions

If you have another python distribution (Conda, Miniconda, Micromamba, Miniforge, _etc._) installed on your laptop skip to the [next step](#env-install). Otherwise,

1. Download the appropriate version of [Miniforge for your operating system](https://github.com/conda-forge/miniforge?tab=readme-ov-file#miniforge3).

   * [Windows](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe)
   * [MacOS x86_64](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh)
   * [MacOS Apple Silicon (arm64)](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh)
   * [Linux x86_64](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh)
   * [Linux aarch64 (arm64)](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh)

2. For Windows operating systems, double-click on the downloaded executable installation file. Do not change the default for the `Add Miniforge3 to my PATH environment variable` so that Miniforge does not cause conflicts with existing installed software.

3. For MacOS and Linux operating systems, open a terminal in the directory that the installation script was downloaded to. Run

    ```shell
    sh Miniforge-pypy3-OS-arch.sh
    ```

   where `OS-arch` above is the operating system and architecture (MacOSX-x86_64, MacOSX-arm64, Linux-x86_64, or Linux-aarch64).

# <a id='env-install'></a>Python environment installation instructions

For Windows operating systems, open the "Miniforge Prompt" installed to the start menu. For MacOS and Linux operating systems, open a terminal. Navigate to the directory containing this file (`LPR_redux/getting_started`) and type the following command

```shell
mamba env create -f environment.yml
```

This will create a new Python environment called `pycap` with all the necessary packages installed. If you do not have `mamba` installed, you can use `conda` instead:

```shell
conda env create -f environment.yml
```

To activate the environment, type

```shell
conda activate pycap
``` 