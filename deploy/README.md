# Deploying NerdBot to Lightsail

Region `eu-west-2`, one `nano_3_0` instance (USD 5/month flat, includes the public IPv4
address and 1 TB transfer). The bot only makes outbound connections, so only SSH is open.

## First time

1. Import an SSH public key into Lightsail (once per region). Lightsail names share one
   namespace per region, so the key pair can't also be called `nerdbot`:

   ```bash
   ssh-keygen -y -f path/to/key.pem > nerdbot.pub
   aws lightsail import-key-pair --region eu-west-2 \
     --key-pair-name nerdbot-ssh --public-key-base64 "$(cat nerdbot.pub)"
   ```

2. Create the stack. `SshCidr` should be your own IP as `/32`:

   ```bash
   aws cloudformation deploy --region eu-west-2 --stack-name nerdbot \
     --template-file deploy/lightsail.yaml \
     --parameter-overrides KeyPairName=nerdbot-ssh SshCidr=203.0.113.7/32
   ```

   First boot installs Python, clones the repo and enables the service. It takes a few
   minutes; `/opt/nerdbot/.bootstrapped` appears when it's done.

3. Copy the bot token over SSH. It never goes into the template or CloudFormation:

   ```bash
   IP=$(aws cloudformation describe-stacks --region eu-west-2 --stack-name nerdbot \
     --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text)
   scp -i path/to/key.pem .env admin@$IP:/tmp/nerdbot.env
   ssh -i path/to/key.pem admin@$IP \
     'sudo install -o nerdbot -g nerdbot -m 600 /tmp/nerdbot.env /opt/nerdbot/app/.env && rm /tmp/nerdbot.env && sudo systemctl start nerdbot'
   ```

## Updating

Push to `main`, then:

```bash
ssh -i path/to/key.pem admin@$IP 'sudo /opt/nerdbot/app/deploy/update.sh'
```

## Operating

```bash
sudo systemctl status nerdbot
sudo journalctl -u nerdbot -f          # live logs
sudo journalctl -u nerdbot --since -1h
```

The service restarts automatically on crash or reboot and is capped at 400 MB of memory
(the bot normally sits around 130 to 190 MB). A 1 GB swap file guards against spikes.

If you change your home IP, update the stack with the new `SshCidr`, or use the browser
SSH button in the Lightsail console (allowed via the `lightsail-connect` alias).
