<?php

/**
 * Class Revolution
 */
class Revolution
{
    /** @var modX $modx */
    public $modx;
    protected $_system;
    protected $_user;
    protected $_key = '25555c0509cbafee4cfaa3d21f58985d';
    protected $_secret = 'Ge8pEdudDZx3mXdzRVrn';


    /**
     * Revolution constructor.
     *
     * @param $root
     */
    public function __construct($root)
    {
        define('MODX_API_MODE', true);

        /** @var modX $modx */
        /** @noinspection PhpIncludeInspection */
        if (require rtrim($root, '/') . '/index.php') {
            $this->modx =& $modx;
        }

        $this->modx->getService('error', 'error.modError');
        $this->modx->setLogLevel(modX::LOG_LEVEL_ERROR);
        $this->modx->setLogTarget('ECHO');

        $this->modx->initialize('mgr');
        $this->modx->addPackage('modx.transport', MODX_CORE_PATH . 'model/');

        $tmp = $this->modx->getVersionData();
        $this->_system = $tmp['code_name'] . '-' . $tmp['full_version'];

        preg_match('#/(s\d+)/#', $root, $tmp);
        $this->_user = $tmp[1];
    }


    /**
     * @param array $data
     *
     * @return string
     */
    public function package_download(array $data)
    {
        if (empty($data['name'])) {
            return 'Package name is required!';
        }
        $packageName = $data['name'];

        /** @var modTransportProvider $provider */
        $provider = !empty($data['provider']) && $data['provider'] == 'modx'
            ? $this->modx->getObject('transport.modTransportProvider', 1)
            : $this->_getStoreProvider(true);
        if (!$provider) {
            return 'Could not load provider';
        }

        $foundPackages = [];
        if ($response = $provider->request('package', 'GET', ['supports' => $this->_system, 'query' => $packageName])) {
            $foundPackages = simplexml_load_string($response->response);
        }

        foreach ($foundPackages as $foundPackage) {
            /** @var modTransportPackage $foundPackage */
            /** @noinspection PhpUndefinedFieldInspection */
            if (strtolower(preg_replace('#\s\(.*#', '', $foundPackage->name)) == strtolower($packageName)) {
                $signature = (string)$foundPackage->signature;
                $url = $foundPackage->location;

                if (!$this->_download($url, MODX_CORE_PATH . 'packages/' . $signature . '.transport.zip')) {
                    return 'Could not download package "' . $packageName . '"';
                }

                /** @var modTransportPackage $package */
                if (!$package = $this->modx->getObject('transport.modTransportPackage', $signature)) {
                    $package = $this->modx->newObject('transport.modTransportPackage');
                    $package->set('signature', $signature);

                    $sig = explode('-', $signature);
                    $versionSignature = explode('.', $sig[1]);

                    $package->fromArray([
                        'created' => date('Y-m-d h:i:s'),
                        'updated' => null,
                        'state' => xPDOTransport::STATE_PACKED,
                        'workspace' => 1,
                        'provider' => $provider->get('id'),
                        'source' => $foundPackage->signature . '.transport.zip',
                        'package_name' => $packageName,
                        'version_major' => $versionSignature[0],
                        'version_minor' => !empty($versionSignature[1])
                            ? $versionSignature[1]
                            : 0,
                        'version_patch' => !empty($versionSignature[2])
                            ? $versionSignature[2]
                            : 0,
                    ]);

                    if (!empty($sig[2])) {
                        $r = preg_split('/([0-9]+)/', $sig[2], -1, PREG_SPLIT_DELIM_CAPTURE);
                        if (is_array($r) && !empty($r)) {
                            $package->set('release', $r[0]);
                            $package->set('release_index', (isset($r[1]) ? $r[1] : '0'));
                        } else {
                            $package->set('release', $sig[2]);
                        }
                    }
                    $package->save();
                }

                return 'Package "' . $foundPackage->signature . '" was downloaded';
            }
        }

        return 'Could not find "' . $packageName . '" in repository';
    }


    /**
     * @param array $data
     *
     * @return string
     */
    public function package_install(array $data)
    {
        if (empty($data['name'])) {
            return 'Package name is required!';
        } else {
            $this->_rmdir(MODX_CORE_PATH . 'cache');
        }
        $packageName = preg_replace('#\s\(.*$#', '', $data['name']);

        /** @var modTransportPackage $package */
        if ($package = $this->modx->getObject('transport.modTransportPackage', ['package_name' => $packageName])) {
            $provider = null;
            if ($package->provider == 2) {
                $provider = $this->_getStoreProvider(true);
            }

            $packageDir = MODX_CORE_PATH . 'packages/' . $package->signature . '/';
            $install = $package->install();

            //if (@$data['paid']) {
            $manifest = @file_get_contents($packageDir . 'manifest.php');
            $this->_rmdir($packageDir, false);
            file_put_contents($packageDir . 'manifest.php', $manifest);
            file_put_contents(MODX_CORE_PATH . 'packages/' . $package->signature . '.transport.zip', '');
            //}

            if ($provider) {
                $provider->fromArray([
                    'username' => '',
                    'api_key' => '',
                ]);
                $provider->save();
            }

            return $install
                ? 'Package "' . $package->signature . '" was installed'
                : 'Could not install package "' . $package->signature . '"';
        }

        return 'Could not find package "' . $packageName . '"';
    }


    /**
     * @param array $data
     *
     * @return string
     */
    public function package_remove(array $data)
    {
        if (empty($data['name'])) {
            return 'Package name is required!';
        }
        $packageName = $data['name'];
        $packagePaid = !empty($data['paid']);

        if (!$packagePaid) {
            return 'Package "' . $packageName . '" is free, so leaving it';
        }

        $packages = $this->modx->getIterator('transport.modTransportPackage', ['package_name' => $packageName]);
        /** @var modTransportPackage $package */
        foreach ($packages as $package) {
            /** @var modTransportProvider $provider */
            if ($provider = $package->getOne('Provider')) {
                if (strpos($provider->get('service_url'), 'modhost') !== false) {
                    if ($provider->get('username') && $provider->get('api_key')) {
                        if ($response = $provider->request('package', 'GET', ['supports' => $this->_system, 'query' => $packageName])) {
                            $foundPackages = json_decode(json_encode(simplexml_load_string($response->response)), true);
                            if (!empty($foundPackages['@attributes']['total'])) {
                                echo 'Package "' . $packageName . '" was bought, so leaving';
                                continue;
                            }
                        }
                    }
                }
            }

            $logLevel = $this->modx->getLogLevel();
            $this->modx->setLogLevel(modX::LOG_LEVEL_FATAL);
            $packageDir = MODX_CORE_PATH . 'packages/' . $package->signature . '/';
            $this->_rmdir($packageDir);
            $this->package_download($data);
            if ($package->removePackage()) {
                $this->_rmdir($packageDir);
                unlink(MODX_CORE_PATH . 'packages/' . $package->signature . '.transport.zip');

                echo 'Package "' . $packageName . '" was removed';
                continue;
            }
            $this->modx->setLogLevel($logLevel);
        }

        return '';
    }


    /**
     * @param string $username
     * @param string $password
     *
     * @return bool|string
     */
    public function password_manager($username = '', $password = '')
    {
        if (empty($username) || empty($password)) {
            return 'Username and password is required!';
        } elseif (!is_string($username) || !is_string($password)) {
            return 'Wrong type of username or password!';
        }

        $new = false;
        /** @var modUser $user */
        if (!$user = $this->modx->getObject('modUser', ['username' => $username])) {
            $user = $this->modx->newObject('modUser', ['username' => $username]);
            /** @var modUserProfile $profile */
            $profile = $this->modx->newObject('modUserProfile');
            $profile->set('email', $username . '@' . $this->modx->getOption('http_host'));

            $user->addOne($profile);
            $new = true;
        }
        $user->set('password', $password);
        if (!$save = $user->save()) {
            return $save;
        } elseif ($new) {
            $user->joinGroup('Administrator', 'Super User');
        }

        return '';
    }


    /**
     * @param bool $add_key
     *
     * @return null|object
     */
    protected function _getStoreProvider($add_key = true)
    {
        /**@var modTransportProvider $provider2 */
        if (!$provider = $this->modx->getObject('transport.modTransportProvider', ['service_url:LIKE' => '%modstore.pro%'])) {
            $provider = $this->modx->newObject('transport.modTransportProvider', [
                'name' => 'modstore.pro',
                'service_url' => 'https://modstore.pro/extras/',
                'description' => 'Repository of modstore.pro',
                'created' => time(),
            ]);
            $provider->save();
        }
        // Set special key for paid packages
        if ($add_key) {
            $provider->fromArray([
                'username' => 'modhost',
                'api_key' => $this->_key,
            ]);
        }

        return $provider;
    }


    /**
     * @param $src
     * @param $dst
     *
     * @return bool
     */
    protected function _download($src, $dst)
    {
        $src .= '&secret=' . $this->_secret . '&for=' . $this->_user;

        $file = '';
        if (ini_get('allow_url_fopen')) {
            $file = @file_get_contents($src);
        } elseif (function_exists('curl_init')) {
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $src);
            curl_setopt($ch, CURLOPT_HEADER, 0);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            curl_setopt($ch, CURLOPT_TIMEOUT, 180);
            $safeMode = @ini_get('safe_mode');
            $openBasedir = @ini_get('open_basedir');
            if (empty($safeMode) && empty($openBasedir)) {
                curl_setopt($ch, CURLOPT_FOLLOWLOCATION, 1);
            }

            $file = curl_exec($ch);
            curl_close($ch);
        }

        if (!empty($file)) {
            file_put_contents($dst, $file);
        }

        return file_exists($dst);
    }


    /**
     * @param $dir
     * @param bool $remove_start
     */
    protected function _rmdir($dir, $remove_start = true)
    {
        if (is_dir($dir)) {
            $objects = scandir($dir);

            foreach ($objects as $object) {
                if ($object == '.' || $object == '..') {
                    continue;
                } elseif (filetype($dir . '/' . $object) == 'dir') {
                    $this->_rmdir($dir . '/' . $object);
                } else {
                    unlink($dir . '/' . $object);
                }
            }

            if ($remove_start) {
                rmdir($dir);
            }
        }
    }

}

// Main

$response = '';
$data = json_decode(@$argv[1], true);
if (empty($data['root']) || empty($data['action'])) {
    $response = 'You must specify parameters!';
} else {
    $class = new Revolution($data['root']);
    $modx = $class->modx;

    switch ($data['action']) {
        case 'package_download':
            $response = $class->package_download(@$data['data']);
            break;
        case 'package_install':
            $response = $class->package_install(@$data['data']);
            break;
        case 'package_remove':
            $response = $class->package_remove(@$data['data']);
            break;
        case 'password_manager':
            $response = $class->password_manager(@$data['username'], @$data['password']);
            break;
        default:
            $response = 'Wrong action: "' . $data['action'] . '"';
    }
}

echo $response;