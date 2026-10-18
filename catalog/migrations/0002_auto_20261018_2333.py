import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductPriceHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_price', models.PositiveIntegerField(verbose_name='Старая цена')),
                ('new_price', models.PositiveIntegerField(verbose_name='Новая цена')),
                ('changed_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата изменения')),
                ('product_info', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='catalog.productinfo', verbose_name='Информация о продукте')),
            ],
            options={
                'verbose_name': 'История цены товара',
                'verbose_name_plural': 'История цен товаров',
                'ordering': ('-changed_at',),
            },
        ),
    ]
