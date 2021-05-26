<?php

$root = '/jail/home/';
$nginx = '/etc/nginx/sites-available/';
$php = '/etc/php5/fpm/pool.d/';

$sites = scandir($root);

foreach ($sites as $i => $site) {
	if ($site[0] == '.' || $site[0] != 's') {continue;}

	$port = 10000 + preg_replace('/\D/', '', $site);

	$nginx_conf = $nginx . $site . '.conf';
	if ($nginx_tmp = @file_get_contents($nginx_conf)) {
		$nginx_tmp = str_replace(
			array(
				"server unix:/var/run/php5-$site.sock;",
				"/jail/home/",
			),
			array(
				"\n\tserver 127.0.0.1:$port;\n",
				"/home/",
			),
			$nginx_tmp
		);
		if (strpos($nginx_tmp, 'modhost') === false) {
			$nginx_tmp = preg_replace("#$site\.(h\d)\.simpledream\.ru#", "$0 $site.$1.modhost.pro", $nginx_tmp);
		}
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}

	$php_conf = $php . $site . '.conf';
	if ($php_tmp = @file_get_contents($php_conf)) {
		$php_tmp = str_replace(
			array(
				"listen = /var/run/php5-$site.sock\nlisten.mode = 0666",
				"/jail/home/"
			),
			array(
				"listen = 127.0.0.1:$port\nlisten.owner = {$site}\nlisten.group = {$site}\nlisten.mode = 0660\nlisten.backlog = -1\nlisten.allowed_clients = 127.0.0.1\n",
				"/home/"
			),
			$php_tmp
		);
		if (strpos($php_tmp, 'chroot') === false) {
			$php_tmp = str_replace(
				array(
					"chdir = /home/$site",
				),
				array(
					"chroot = /jail/\nchdir = /home/$site",
				),
				$php_tmp
			);
		}
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}
	if ($site == 'test23') {
	}

	$xml_conf = $root . $site . '/config.xml';
	if ($xml_tmp = @file_get_contents($xml_conf)) {
		$xml_tmp = str_replace(
			array(
				'localhost',
				'/jail/home/'
			),
			array(
				'127.0.0.1',
				'/home/'
			),
			$xml_tmp
		);
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}

	$config_conf = $root . $site . '/www/core/config/config.inc.php';
	if ($config_tmp = @file_get_contents($config_conf)) {
		$config_tmp = str_replace(
			array(
				'localhost',
				'/jail/home/'
			),
			array(
				'127.0.0.1',
				'/home/'
			),
			$config_tmp
		);
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}

	$core_conf = $root . $site . '/www/config.core.php';
	if ($core_tmp = @file_get_contents($core_conf)) {
		$core_tmp = str_replace(
			array(
				'/jail/home/'
			),
			array(
				'/home/'
			),
			$core_tmp
		);
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}

	$manager_conf = $root . $site . '/www/manager/config.core.php';
	if ($manager_tmp = @file_get_contents($manager_conf)) {
		$manager_tmp = str_replace(
			array(
				'/jail/home/'
			),
			array(
				'/home/'
			),
			$manager_tmp
		);
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}
	
	$connectors_conf = $root . $site . '/www/connectors/config.core.php';
	if ($connectors_tmp = @file_get_contents($connectors_conf)) {
		$connectors_tmp = str_replace(
			array(
				'/jail/home/'
			),
			array(
				'/home/'
			),
			$connectors_tmp
		);
	}
	else {
		echo "Unable to open site {$site}\n";
		continue;
	}

	file_put_contents($nginx_conf, $nginx_tmp);
	file_put_contents($php_conf, $php_tmp);
	file_put_contents($xml_conf, $xml_tmp);
	file_put_contents($config_conf, $config_tmp);
	file_put_contents($core_conf, $core_tmp);
	file_put_contents($manager_conf, $manager_tmp);
	file_put_contents($connectors_conf, $connectors_tmp);

	shell_exec("rm -rf $root$site/www/core/cache/");
}

shell_exec("service nginx restart");
shell_exec("service php5-fpm stop && sleep 1 && service php5-fpm start");