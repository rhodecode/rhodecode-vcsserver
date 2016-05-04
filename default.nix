# Nix environment for the community edition
#
# This shall be as lean as possible, just producing the rhodecode-vcsserver
# derivation. For advanced tweaks to pimp up the development environment we use
# "shell.nix" so that it does not have to clutter this file.

{ pkgs ? (import <nixpkgs> {})
, pythonPackages ? "python27Packages"
, pythonExternalOverrides ? self: super: {}
, doCheck ? true
}:

let pkgs_ = pkgs; in

let
  pkgs = pkgs_.overridePackages (self: super: {
    # Override subversion derivation to
    #  - activate python bindings
    #  - set version to 1.8
    subversion = super.subversion18.override {
       httpSupport = true;
       pythonBindings = true;
       python = self.python27Packages.python;
    };
  });

  inherit (pkgs.lib) fix extends;

  basePythonPackages = with builtins; if isAttrs pythonPackages
    then pythonPackages
    else getAttr pythonPackages pkgs;

  elem = builtins.elem;
  basename = path: with pkgs.lib; last (splitString "/" path);
  startsWith = prefix: full: let
    actualPrefix = builtins.substring 0 (builtins.stringLength prefix) full;
  in actualPrefix == prefix;

  src-filter = path: type: with pkgs.lib;
    let
      ext = last (splitString "." path);
    in
      !elem (basename path) [
        ".git" ".hg" "__pycache__" ".eggs" "node_modules"
        "build" "data" "tmp"] &&
      !elem ext ["egg-info" "pyc"] &&
      !startsWith "result" path;

  rhodecode-vcsserver-src = builtins.filterSource src-filter ./.;

  pythonGeneratedPackages = self: basePythonPackages.override (a: {
    inherit self;
  })
  // (scopedImport {
    self = self;
    super = basePythonPackages;
    inherit pkgs;
    inherit (pkgs) fetchurl fetchgit;
  } ./pkgs/python-packages.nix);

  pythonOverrides = import ./pkgs/python-packages-overrides.nix {
    inherit
      basePythonPackages
      pkgs;
  };

  pythonLocalOverrides = self: super: {
    rhodecode-vcsserver = super.rhodecode-vcsserver.override (attrs: {
      src = rhodecode-vcsserver-src;
      inherit doCheck;

      propagatedBuildInputs = attrs.propagatedBuildInputs ++ ([
        pkgs.git
        pkgs.subversion
      ]);

      # TODO: johbo: Make a nicer way to expose the parts. Maybe
      # pkgs/default.nix?
      passthru = {
        pythonPackages = self;
      };

      # Somewhat snappier setup of the development environment
      # TODO: move into shell.nix
      # TODO: think of supporting a stable path again, so that multiple shells
      #       can share it.
      shellHook = ''
        # Set locale
        export LC_ALL="en_US.UTF-8"

        tmp_path=$(mktemp -d)
        export PATH="$tmp_path/bin:$PATH"
        export PYTHONPATH="$tmp_path/${self.python.sitePackages}:$PYTHONPATH"
        mkdir -p $tmp_path/${self.python.sitePackages}
        python setup.py develop --prefix $tmp_path --allow-hosts ""
      '';

      # Add VCSServer bin directory to path so that tests can find 'vcsserver'.
      preCheck = ''
        export PATH="$out/bin:$PATH"
      '';

      postInstall = ''
        echo "Writing meta information for rccontrol to nix-support/rccontrol"
        mkdir -p $out/nix-support/rccontrol
        cp -v vcsserver/VERSION $out/nix-support/rccontrol/version
        echo "DONE: Meta information for rccontrol written"

        ln -s ${self.pyramid}/bin/* $out/bin  #*/
        ln -s ${self.gunicorn}/bin/gunicorn $out/bin/

        # Symlink version control utilities
        #
        # We ensure that always the correct version is available as a symlink.
        # So that users calling them via the profile path will always use the
        # correct version.
        ln -s ${pkgs.git}/bin/git $out/bin
        ln -s ${self.mercurial}/bin/hg $out/bin
        ln -s ${pkgs.subversion}/bin/svn* $out/bin

        for file in $out/bin/*; do  #*/
          wrapProgram $file \
            --prefix PYTHONPATH : $PYTHONPATH \
            --set PYTHONHASHSEED random
        done
      '';

    });
  };

  # Apply all overrides and fix the final package set
  myPythonPackages =
    (fix
    (extends pythonExternalOverrides
    (extends pythonLocalOverrides
    (extends pythonOverrides
             pythonGeneratedPackages))));

in myPythonPackages.rhodecode-vcsserver
