{ pkgs ? import <nixpkgs> {}
}:

let

  vcsserver = import ./default.nix {
    inherit
      pkgs;
  };

in {
  build = vcsserver;
}
