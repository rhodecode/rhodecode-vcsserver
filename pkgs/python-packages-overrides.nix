# Overrides for the generated python-packages.nix
#
# This function is intended to be used as an extension to the generated file
# python-packages.nix. The main objective is to add needed dependencies of C
# libraries and tweak the build instructions where needed.

{ pkgs, basePythonPackages }:

let
  sed = "sed -i";
in

self: super: {

  subvertpy = super.subvertpy.override (attrs: {
    SVN_PREFIX = "${pkgs.subversion}";
    propagatedBuildInputs = attrs.propagatedBuildInputs ++ [
      pkgs.aprutil
      pkgs.subversion
    ];
    preBuild = pkgs.lib.optionalString pkgs.stdenv.isDarwin ''
      ${sed} -e "s/'gcc'/'clang'/" setup.py
    '';
  });

  mercurial = super.mercurial.override (attrs: {
    propagatedBuildInputs = attrs.propagatedBuildInputs ++ [
      self.python.modules.curses
    ] ++ pkgs.lib.optional pkgs.stdenv.isDarwin
      pkgs.darwin.apple_sdk.frameworks.ApplicationServices;
  });

  pyramid = super.pyramid.override (attrs: {
    postFixup = ''
      wrapPythonPrograms
      # TODO: johbo: "wrapPython" adds this magic line which
      # confuses pserve.
      ${sed} '/import sys; sys.argv/d' $out/bin/.pserve-wrapped
    '';
  });

  Pyro4 = super.Pyro4.override (attrs: {
    # TODO: Was not able to generate this version, needs further
    # investigation.
    name = "Pyro4-4.35";
    src = pkgs.fetchurl {
      url = "https://pypi.python.org/packages/source/P/Pyro4/Pyro4-4.35.src.tar.gz";
      md5 = "cbe6cb855f086a0f092ca075005855f3";
    };
  });

  # Avoid that setuptools is replaced, this leads to trouble
  # with buildPythonPackage.
  setuptools = basePythonPackages.setuptools;

}
