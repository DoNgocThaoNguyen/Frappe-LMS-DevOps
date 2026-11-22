pipeline {
    parameters {
        string(name: 'GHA_RUN_ID', defaultValue: '', trim: true,
               description: 'GitHub Actions run ID. Leave blank to run the digest tests only.')
        string(name: 'EC2_HOST', defaultValue: '', trim: true,
               description: 'Current public IPv4 address of the Cloud EC2 instance.')
    }

    agent any

    stages {
        stage('Identify revision') {
            steps {
                sh 'git rev-parse HEAD'
            }
        }

        stage('Test release digest') {
            steps {
                dir('deploy') {
                    sh 'python3 -B -m unittest -v test_release_digest test_prepare_cloud_release'
                }
            }
        }

        stage('Read release candidate') {
            when {
                expression { return (params.GHA_RUN_ID ?: '').trim() != '' }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'github-dacn-read',
                    usernameVariable: 'DACN_GH_USER',
                    passwordVariable: 'GH_TOKEN'
                )]) {
                    script {
                        def manifest = sh(
                            label: 'Verify the GitHub Actions release candidate',
                            script: 'python3 -B deploy/read_release_candidate.py "$GHA_RUN_ID"',
                            returnStdout: true
                        )
                        writeFile file: 'release-candidate.json', text: manifest
                    }
                }
                archiveArtifacts artifacts: 'release-candidate.json'
                stash name: 'verified-release-candidate', includes: 'release-candidate.json'
            }
        }

        stage('Approve release candidate') {
            when {
                expression { return (params.GHA_RUN_ID ?: '').trim() != '' }
            }
            steps {
                unstash 'verified-release-candidate'
                script {
                    def manifest = readFile(file: 'release-candidate.json', encoding: 'UTF-8').trim()
                    timeout(time: 30, unit: 'MINUTES') {
                        def approver = input(
                            message: "Approve this verified release candidate?\n\n${manifest}",
                            ok: 'Approve candidate',
                            submitterParameter: 'APPROVED_BY'
                        )
                        echo "APPROVED by ${approver}\n${manifest}"
                    }
                }
            }
        }
        stage('Deploy approved Cloud release') {
            when {
                expression { return (params.GHA_RUN_ID ?: '').trim() != '' }
            }
            steps {
                unstash 'verified-release-candidate'

                withCredentials([usernamePassword(
                    credentialsId: 'ghcr-readonly',
                    usernameVariable: 'GHCR_READ_USER',
                    passwordVariable: 'GHCR_READ_TOKEN'
                )]) {
                    sh '''
                        set +x
                        set -eu
                        python3 -B deploy/prepare_cloud_release.py \
                          --manifest release-candidate.json \
                          --stable deploy/cloud/last_known_good_cloud.json \
                          --run-id "$GHA_RUN_ID" \
                          --output approved-cloud-vars.json
                        python3 -c 'import ipaddress, os; ipaddress.IPv4Address(os.environ["EC2_HOST"])'
                        ansible-playbook -i "$EC2_HOST," -c ssh -u ubuntu \
                          --private-key /opt/dacn/ec2-key \
                          --ssh-common-args='-o IdentitiesOnly=yes -o UserKnownHostsFile=/opt/dacn/known_hosts -o StrictHostKeyChecking=yes' \
                          -e @approved-cloud-vars.json \
                          deploy/cloud/deploy_cloud.yml
                    '''
                }
            }
        }
    }
}
