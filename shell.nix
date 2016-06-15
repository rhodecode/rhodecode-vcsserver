{ pkgs ? import <nixpkgs> {}
,  doCheck ? false
}:

let
  vcsserver = import ./default.nix {
    inherit
      doCheck
      pkgs;
  };

in vcsserver.override (attrs: {

  # Avoid that we dump any sources into the store when entering the shell and
  # make development a little bit more convenient.
  src = null;

})
