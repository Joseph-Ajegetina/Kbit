# Generated by Django 3.1.2 on 2020-11-23 14:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_couponcode'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='CouponCode',
            new_name='Coupon',
        ),
        migrations.AddField(
            model_name='order',
            name='coupon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.coupon'),
        ),
    ]
