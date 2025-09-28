from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import YaAccountSelizalier
from datetime import datetime, timedelta
from .models import YaAccountModel
class YaAccountAPIView(APIView):
    def get(self, request, *args, **kwargs):
        need_update_accounts = YaAccountModel.objects.all()
        return Response({'status':'success','data':YaAccountSelizalier(need_update_accounts,many=True).data})
    def post(self,request,*args,**kwargs):
        data = request.data
        name = data.get('name')
        try:
            account = YaAccountModel.objects.get(name=name)
            return Response({'status':'success','data':YaAccountSelizalier(account).data})
        except:
            pass
        city = data.get('city')
        categories = data.get('categories')
        new_cats = data.get('new_cats')
        del_cats = data.get('del_cats')
        new_city = data.get('new_city')
        need_update = data.get('need_update')
        new = YaAccountModel.objects.create(name=name,city=city,categories='\n'.join(categories),new_cats=new_cats,new_city=new_city,del_cats=del_cats,need_update=need_update)
        return Response({'status':'success','data':YaAccountSelizalier(new).data})
    def patch(self,request,*args,**kwargs):
        data = request.data
        account_name = data.get('name')
        try:
            account = YaAccountModel.objects.get(name=account_name)
        except:
            return Response({"status":'failed','data':"Account not found"})
        added_cats = data.get('added_cats')
        if added_cats is not None:
            cur_cats = [i.replace('\r','').replace('\n','') for i in account.categories.split('\n') if i != '']
            new_cats = [i.replace('\r','').replace('\n','') for i in account.new_cats.split('\n') if i != '']
            new_cats = [] if new_cats is None else list(set(new_cats))
            for added_cat in added_cats.split('\n'):
                if added_cat not in cur_cats:
                    cur_cats.append(added_cat)
                    new_cats.remove(added_cat)
            account.categories = '\n'.join(list(set(cur_cats)))
            if new_cats is not None and len(new_cats) != 0:
                account.new_cats = '\n'.join(list(set(new_cats)))
            else:
                account.new_cats = ''
        deleted_cats = data.get('deleted_cats')
        if deleted_cats is not None:
            cur_cats = [i.replace('\r', '').replace('\n', '') for i in account.categories.split('\n') if i != '']
            cur_cats = [] if cur_cats is None else list(set(cur_cats))
            del_cats = [i.replace('\r', '').replace('\n', '') for i in account.del_cats.split('\n') if i != '']
            del_cats = [] if del_cats is None else list(set(del_cats))
            for deleted_cat in deleted_cats.split('\n'):
                cur_cats.remove(deleted_cat)
                del_cats.remove(deleted_cat)
            account.categories = '\n'.join(list(set(cur_cats)))
            if del_cats is not None and len(del_cats) != 0:
                account.del_cats = '\n'.join(list(set(del_cats)))
            else:
                account.del_cats = ''
        new_city = data.get('new_city')
        if new_city is not None:
            account.city = new_city
        if account.new_cats == '' and account.del_cats == '' and account.new_city == '':
            account.need_update = False
        account.save()
        return Response({"status":'success','message':"Изменения внесены!"})


    def put(self,request,*args,**kwargs):
        data = request.data
        account_name = data.get('name')
        try:
            account = YaAccountModel.objects.get(name=account_name)
        except:
            return Response({"status":'failed','data':"Account not found"})
        added_cats = data.get('added_cats')
        if added_cats is not None:
            new_cats = [i.replace('\r','').replace('\n','') for i in account.new_cats.split('\n') if i != '']
            del_cats = [i.replace('\r', '').replace('\n', '') for i in account.del_cats.split('\n') if
                        i != ''] if account.del_cats != '' else []
            new_cats = [] if new_cats is None else list(set(new_cats))
            for added_cat in added_cats.split('\n'):
                if added_cat not in new_cats:
                    new_cats.append(added_cat)
                if added_cat in del_cats:
                    del_cats.remove(added_cat)
            if del_cats is not None and len(del_cats) != 0:
                account.del_cats = '\n'.join(list(set(del_cats)))
            else:
                account.del_cats = ''
            if new_cats is not None and len(new_cats) != 0:
                account.new_cats = '\n'.join(list(set(new_cats)))
            else:
                account.new_cats = ''
            account.need_update = True
        deleted_cats = data.get('deleted_cats')
        if deleted_cats is not None:
            new_cats = [i.replace('\r', '').replace('\n', '') for i in account.new_cats.split('\n') if i != '']
            del_cats = [i.replace('\r', '').replace('\n', '') for i in account.del_cats.split('\n') if i != ''] if account.del_cats != '' else []
            print(f'del_cats - ({del_cats}). account.del_cats - ({account.del_cats}), {account.del_cats != ""}')
            # del_cats = [] if del_cats is None else list(set(del_cats))
            for deleted_cat in deleted_cats.split('\n'):
                if deleted_cat not in del_cats:
                    del_cats.append(deleted_cat)
                if deleted_cat in new_cats:
                    new_cats.remove(deleted_cat)
            if del_cats is not None and len(del_cats) != 0:
                account.del_cats = '\n'.join(list(set(del_cats)))
            else:
                account.del_cats = ''

            if new_cats is not None and len(new_cats) != 0:
                account.new_cats = '\n'.join(list(set(new_cats)))
            else:
                account.new_cats = ''
            account.need_update = True
        new_city = data.get('new_city')
        if new_city is not None:
            account.new_city = new_city
            account.need_update = True
        account.save()
        return Response({"status":'success','message':"Изменения внесены!"})