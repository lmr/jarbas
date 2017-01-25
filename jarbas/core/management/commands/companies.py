import csv
import lzma

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from jarbas.core.management.commands import LoadCommand
from jarbas.core.models import Company


class Command(LoadCommand):
    help = 'Load Serenata de Amor companies dataset into the database'
    
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--batch-size', '-b', dest='batch_size', 
                type=int, default=10000, 
                help='Number of documents to be created at a time')

    def handle(self, *args, **options):
        self.path = options['dataset']
        self.count = self.print_count(Company)
        print('Starting with {:,} companies'.format(self.count))

        if options.get('drop', False):
            self.drop_all(Company)
            self.count = 0

        self.bulk_create_by(self.companies, options['batch_size'])
    
    
    def save_companies(self):
        self.bulk_create_by(self.companies, 10000)

    @property
    def companies(self):
        """
        Receives path to the dataset file and create a Company object for
        each row of each file. It creates the related activity when needed.
        """
        skip=('main_activity','secondary_activity')
        keys = list(f.name for f in Company._meta.fields if f not in skip)
        for num in range(1,100):
            keys.append('secondary_activity_{}_code'.format(num))
            keys.append('secondary_activity_{}'.format(num))
        with lzma.open(self.path, mode='rt') as file_handler:
            for row in csv.DictReader(file_handler):  
               filtered = {k: v for k, v in row.items() if k in keys}
               data = dict(
                       code=row['main_activity_code'],
                       description=row['main_activity']
               )
               filtered['main_activity'] = data
               obj = Company(**self.serialize(filtered))
               
               yield obj
                 
    def serialize_activities(self, row):
        secondaries = {}
        for num in range(1, 100):
            code = row.get('secondary_activity_{}_code'.format(num))
            description = row.get('secondary_activity_{}'.format(num))
            if code and description:
                secondaries[code] = description
        
        if len(secondaries) == 0:
            row['secondary_activity'] = []
        else:
            row['secondary_activity'] = [secondaries]

        for num in range(1,100):
            row.pop('secondary_activity_{}_code'.format(num), None)
            row.pop('secondary_activity_{}'.format(num), None)
        
        
    def serialize(self, row):
        row['email'] = self.to_email(row['email'])

        dates = ('opening', 'situation_date', 'special_situation_date')
        for key in dates:
            row[key] = self.to_date(row[key])

        decimals = ('latitude', 'longitude')
        for key in decimals:
            row[key] = self.to_number(row[key])
        
        self.serialize_activities(row)

        return row

    @staticmethod
    def to_email(email):
        try:
            validate_email(email)
            return email

        except ValidationError:
            return None

    def bulk_create_by(self, companies, size):
        batch = list()
        for company in companies:
            batch.append(company)
            if len(batch) == size:
                Company.objects.bulk_create(batch)
                self.count += len(batch)
                self.print_count(Company, count=self.count)
                batch = list()
        Company.objects.bulk_create(batch)
