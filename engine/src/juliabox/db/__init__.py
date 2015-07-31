__author__ = 'tan'
from db_base import JBoxDB, JBoxDBPlugin, JBoxDBItemNotFound
from user_v2 import JBoxUserV2
from container import JBoxSessionProps
from dynconfig import JBoxDynConfig
from juliabox.cloud.aws import CloudHost
from juliabox.jbox_util import JBoxCfg


def configure():
    JBoxDB.configure()
    tablenames = JBoxCfg.get('db.tables', dict())

    for cls in (JBoxUserV2, JBoxSessionProps, JBoxDynConfig):
        cls.NAME = tablenames.get(cls.NAME, cls.NAME)
        JBoxDB.log_info("%s provided by table %s", cls.__name__, cls.NAME)

    for plugin in JBoxDBPlugin.jbox_get_plugins(JBoxDBPlugin.PLUGIN_TABLE):
        JBoxDB.log_info("Found plugin %r provides %r", plugin, plugin.provides)
        plugin.NAME = tablenames.get(plugin.NAME, plugin.NAME)
        JBoxDB.log_info("%s provided by table %s", plugin.__name__, plugin.NAME)


def is_proposed_cluster_leader():
    if not CloudHost.ENABLED['cloudwatch']:
        return False

    cluster = CloudHost.INSTALL_ID
    leader = JBoxDynConfig.get_cluster_leader(cluster)
    return leader == CloudHost.instance_id()


def is_cluster_leader():
    if not CloudHost.ENABLED['cloudwatch']:
        return False

    cluster = CloudHost.INSTALL_ID
    instances = CloudHost.get_autoscaled_instances()
    leader = JBoxDynConfig.get_cluster_leader(cluster)
    ami_recentness = CloudHost.get_ami_recentness()
    JBoxDB.log_debug("cluster: %s. instances: %s. leader: %s. ami_recentness: %d",
                     cluster, repr(instances), repr(leader), ami_recentness)

    # if none set, or set instance is dead elect self as leader, but wait till next cycle to prevent conflicts
    if (leader is None) or (leader not in instances) and (ami_recentness >= 0):
        JBoxDB.log_info("setting self (%s) as cluster leader", CloudHost.instance_id())
        JBoxDynConfig.set_cluster_leader(cluster, CloudHost.instance_id())
        return False

    is_leader = (leader == CloudHost.instance_id())

    # if running an older ami, step down from cluster leader
    if (ami_recentness < 0) and is_leader:
        JBoxDB.log_info("unmarking self (%s) as cluster leader", CloudHost.instance_id())
        JBoxDynConfig.unset_cluster_leader(cluster)
        return False

    return is_leader


def publish_stats():
    JBoxUserV2.calc_stats()
    JBoxDynConfig.set_stat(CloudHost.INSTALL_ID, JBoxUserV2.STAT_NAME, JBoxUserV2.STATS)