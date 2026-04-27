def fix_deplist(deps):
    """ Turn a dependency list into lowercase, and make sure all entries
        that are just a string become a tuple of strings
    """
    deps = [
        ((dep.lower(),)
         if not isinstance(dep, (list, tuple))
         else tuple([dep_entry.lower()
                     for dep_entry in dep
                    ]))
        for dep in deps
    ]
    return deps
