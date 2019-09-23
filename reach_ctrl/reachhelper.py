def search(name):

    import os.path
    if not os.path.exists(name):

        from pkg_resources import resource_filename
        try:
            name = resource_filename('reach_ctrl', 'config/'+name)
        except Exception as e:
            return None
    
    return name

