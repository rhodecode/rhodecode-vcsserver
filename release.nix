{ pkgs ? import <nixpkgs> {}
, doCheck ? true
}:

let

  vcsserver = import ./default.nix {
    inherit
      doCheck
      pkgs;
  };

in {
  build = vcsserver;
}
