#!/bin/bash

set -o errexit  # Exit the script with error if any of the commands fail

install_composer ()
{
    # See: https://getcomposer.org/doc/faqs/how-to-install-composer-programmatically.md
    EXPECTED_CHECKSUM="$(php -r 'copy("https://composer.github.io/installer.sig", "php://stdout");')"
    php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
    ACTUAL_CHECKSUM="$(php -r "echo hash_file('sha384', 'composer-setup.php');")"

    if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]
    then
        >&2 echo 'ERROR: Invalid installer checksum'
        rm composer-setup.php
        exit 1
    fi

    php composer-setup.php --quiet
    RESULT=$?
    rm composer-setup.php

    if [ $RESULT -ne 0 ]; then
        exit $RESULT
    fi
}

install_extension ()
{
    if [ "x${PHPC_BRANCH}" != "x" ] || [ "x${PHPC_REPO}" != "x" ]; then
        REPO=${PHPC_REPO:-https://github.com/mongodb/mongo-php-driver}
        BRANCH=${PHPC_BRANCH:-master}

        echo "Compiling driver branch ${BRANCH} from repository ${REPO}"

        BUILD_DIR="$(mktemp -d)"

        git clone --depth 1 --recurse-submodules --shallow-submodules --branch ${BRANCH} ${REPO} ${BUILD_DIR}
        pushd ${BUILD_DIR}

        phpize
        ./configure --enable-mongodb-developer-flags
        make all -j20 > /dev/null
        make install

        popd
    elif [ "x${PHPC_VERSION}" != "x" ]; then
        echo "Installing driver version ${PHPC_VERSION} from PECL"
        pecl install -f mongodb-${PHPC_VERSION}
    else
        echo "Installing latest driver version from PECL"
        pecl install -f mongodb
    fi

    echo "extension=mongodb.so" > ${PHP_PATH}/lib/php.ini
}

# TODO: Remove this after https://jira.mongodb.org/browse/BUILD-13026 is resolved
if [ -d "/opt/php/${PHP_VERSION}-64bit/bin" ]; then
    PHP_PATH="/opt/php/${PHP_VERSION}-64bit/bin"
else
    # Try to find the newest version matching our constant
    PHP_PATH=`find /opt/php/ -maxdepth 1 -type d -name "${PHP_VERSION}*-64bit" -print | sort -V -r | head -1`
fi

if [ ! -d "$PHP_PATH" ]; then
    echo "Could not find PHP binaries for version ${PHP_VERSION}. Listing available versions..."
    ls -1 /opt/php
    exit 1
fi

export PATH=${PHP_PATH}/bin:${PATH}
export PHPLIB_PATH="$(pwd)/mongo-php-library"

cd integrations/${DRIVER_DIRNAME}

# Install extension and print its phpinfo()
install_extension
php --ri mongodb

# Install composer and dependencies
install_composer
php composer.phar update --working-dir=${PHPLIB_PATH}

# The symlink helps to include the library and tests with a simple path
ln -s ${PHPLIB_PATH}/vendor ./vendor
