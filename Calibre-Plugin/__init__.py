from calibre.customize import InterfaceActionBase

class KoboXRayPlugin(InterfaceActionBase):
    # Brand new internal ID!
    name                = 'xray_generator'
    description         = 'Sends EPUBs to the local X-Ray Engine for processing.'
    supported_platforms = ['windows', 'osx', 'linux']
    author              = 'Jing'
    version             = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)
    
    # Matches the new ID perfectly
    actual_plugin = 'calibre_plugins.kobo_xray.ui:XRayUI'