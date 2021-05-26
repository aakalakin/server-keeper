<?php

if (!empty($_GET['q']) && $_GET['q'] == 'check') {
    if (!file_exists('/run/mysqld/mysqld.pid') || !file_exists('/run/mysqld/mysqld.sock')) {
        $page = 'MySQL error';
    } elseif (!file_exists('/run/php/php5.6-fpm.pid') || !file_exists('/run/php/php5.6-fpm.sock')) {
        $page = 'PHP 5.6 error';
    } elseif (!file_exists('/run/php/php7.0-fpm.pid') || !file_exists('/run/php/php7.0-fpm.sock')) {
        $page = 'PHP 7.0 error';
    } elseif (!file_exists('/run/php/php7.1-fpm.pid') || !file_exists('/run/php/php7.1-fpm.sock')) {
        $page = 'PHP 7.1 error';
    } elseif (!file_exists('/run/php/php7.2-fpm.pid') || !file_exists('/run/php/php7.2-fpm.sock')) {
        $page = 'PHP 7.2 error';
    } elseif (!file_exists('/run/php/php7.3-fpm.pid') || !file_exists('/run/php/php7.3-fpm.sock')) {
        $page = 'PHP 7.3 error';
    } elseif (!file_exists('/run/php/php7.4-fpm.pid') || !file_exists('/run/php/php7.4-fpm.sock')) {
        $page = 'PHP 7.4 error';
    } else {
        $page = 'All OK';
    }
} else {
    header('HTTP/1.1 503 Service Temporarily Unavailable');
    $page = preg_match('#\bru\b#i', @$_SERVER['HTTP_ACCEPT_LANGUAGE'])
        ? file_get_contents('docs/ru.html')
        : file_get_contents('docs/en.html');
}

echo $page;
